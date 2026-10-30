# -*- coding:utf-8 -*-
"""u2_webview 核心实现：通过 CDP（借助 DrissionPage）无驱动接管 WebView。"""
import atexit
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, List, Optional

from adbutils import adb
from DrissionPage import Chromium, ChromiumOptions
from DrissionPage._base.chromium import Chromium as _Chromium_Class
from DrissionPage._base.driver import BrowserDriver

os.environ["NO_PROXY"] = "127.0.0.1,localhost"

logger = logging.getLogger(__name__)

# /proc/net/unix 中 devtools socket 的命名模式（抽象命名空间 socket 带 '@' 前缀）：
#   @webview_devtools_remote_<pid>        应用内 WebView（后缀 = 宿主进程 pid）
#   @chrome_devtools_remote_<pid>         基于 Chrome 内核的应用进程
#   @chrome_devtools_remote               Chrome 浏览器本体（无 pid 后缀）
#   @<package>_devtools_remote[_<pid>]    部分 Chromium 构建会把包名放进 socket 名
_DEVTOOLS_SOCKET_RE = re.compile(
    r"@?(?P<prefix>[A-Za-z0-9._]+)_devtools_remote(?:_(?P<pid>\d+))?\s*$"
)
# 只按 pid 解析归属、本身不是包名的前缀
_GENERIC_PREFIXES = frozenset({"webview", "chrome"})

# 专用于探活的 opener：绕开系统代理，避免 VPN/Clash 场景下 127.0.0.1 请求被劫持
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@dataclass(frozen=True)
class DevtoolsSocket:
    """设备上发现的一个 devtools 远程调试 socket。"""

    name: str  # socket 名（不含前导 '@'）
    pid: Optional[int] = None  # socket 名中携带的宿主进程 pid（可能为 None）
    package: Optional[str] = None  # 尽力解析出的归属包名（None 表示未知）

    def matches(self, package: Optional[str]) -> bool:
        """按包名过滤时是否应保留该 socket；不过滤（None/空）时全部保留。"""
        if not package:
            return True
        return bool(self.package) and self.package == package


def parse_unix_socket_lines(
    lines: List[str],
    resolve_package: Optional[Callable[[int], Optional[str]]] = None,
) -> List[DevtoolsSocket]:
    """解析 `cat /proc/net/unix` 的输出行，返回 devtools socket 列表。

    包名解析优先级：socket 名内嵌的包名（含 '.' 的前缀）> pid -> /proc/<pid>/cmdline。
    后创建的 socket 在 /proc/net/unix 中排在后面，反转后最新创建的排在最前，
    与旧版 `list(reversed(sockets))` 的行为一致。
    """
    found = {}
    for line in lines:
        match = _DEVTOOLS_SOCKET_RE.search(line.strip())
        if not match:
            continue
        name = match.group(0).lstrip("@").strip()
        if name in found:
            continue
        prefix, pid_text = match.group("prefix"), match.group("pid")
        pid = int(pid_text) if pid_text else None
        if prefix not in _GENERIC_PREFIXES and "." in prefix:
            package: Optional[str] = prefix
        elif pid is not None and resolve_package is not None:
            package = resolve_package(pid)
        else:
            package = None
        found[name] = DevtoolsSocket(name=name, pid=pid, package=package)
    return list(found.values())[::-1]


def probe_devtools_endpoint(port: int, timeout: float = 2.0) -> bool:
    """用一次轻量 HTTP 请求确认转发出来的 devtools 端点是否存活。

    避免对僵尸 socket 直接走重量级的 Chromium 全量连接。
    """
    try:
        with _opener.open(f"http://127.0.0.1:{port}/json/version", timeout=timeout) as resp:
            return resp.status == 200
    except (urllib.error.URLError, OSError, ValueError):
        return False


class Webview:
    def __init__(self, d=None, package: Optional[str] = None):
        """
        :param d: uiautomator2.Device 实例，可先留空后用 init_device 绑定
        :param package: 目标应用包名。设备上同时存在多个 WebView socket 时，
            限定只接管归属该包的 socket，避免连到别的应用。
        """
        self.d = d
        self.package = package
        self.browser = None
        self.local_port = None
        # 兜底清理：无论进程如何退出，都尽量释放本地驱动与端口转发
        atexit.register(self.detach)

    def init_device(self, d):
        self.d = d

    def _get_free_port(self) -> int:
        """让操作系统自动分配一个可用的空闲端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _resolve_package(self, pid: int) -> Optional[str]:
        """尽力通过 /proc/<pid>/cmdline 把 pid 解析成应用包名。"""
        try:
            out = self.d.shell(f"cat /proc/{pid}/cmdline").output.strip().strip("\x00")
            return out or None
        except Exception:
            logger.debug("resolve package for pid %s failed", pid, exc_info=True)
            return None

    def _discover(self) -> List[DevtoolsSocket]:
        """发现设备上所有 devtools socket，并尽力标注归属包名。"""
        if not self.d:
            raise RuntimeError("device not bound; pass d to Webview() or call init_device(d)")
        output = self.d.shell("cat /proc/net/unix | grep -a devtools_remote").output
        lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
        return parse_unix_socket_lines(lines, resolve_package=self._resolve_package)

    def list_devsockets(self) -> List[DevtoolsSocket]:
        """公开的发现接口：返回当前设备上全部 devtools socket（含归属信息），便于调试。"""
        return self._discover()

    def _get_active_sockets(self) -> List[str]:
        """仅返回 socket 名列表（保留旧接口，向后兼容）。"""
        return [s.name for s in self._discover()]

    @staticmethod
    def _stop_browser_drivers(browser) -> None:
        """停止一个 DrissionPage Chromium 实例底层的全部 websocket 驱动。"""
        try:
            if hasattr(browser, "_all_drivers"):
                for driver_set in list(browser._all_drivers.values()):
                    for driver in driver_set:
                        if hasattr(driver, "stop"):
                            driver.stop()
            if hasattr(browser, "_driver") and browser._driver:
                browser._driver.stop()
        except Exception:
            logger.debug("error stopping browser drivers", exc_info=True)

    def attach(self, timeout: float = 20, package: Optional[str] = None):
        """建立连接（核心行为）。

        :param timeout: 轮询 socket 的最长等待秒数
        :param package: 临时覆盖构造时传入的包名过滤条件
        """
        if self.browser:
            return self.browser
        if not self.d:
            raise RuntimeError("device not bound; pass d to Webview() or call init_device(d)")

        target = package or self.package
        device = adb.device(serial=self.d.serial)
        start_time = time.time()

        while time.time() - start_time < timeout:
            candidates = self._discover()
            if target:
                named = [s for s in candidates if s.matches(target)]
                if not named:
                    logger.debug("no devtools socket owned by %s yet; retrying", target)
                    time.sleep(0.5)
                    continue
                candidates = named

            for sock in candidates:
                test_port = self._get_free_port()
                browser = None
                try:
                    device.forward_remove(f"tcp:{test_port}")
                except Exception:
                    pass

                try:
                    device.forward(f"tcp:{test_port}", f"localabstract:{sock.name}")

                    if not probe_devtools_endpoint(test_port):
                        logger.debug("devtools endpoint %s not answering; skip", sock.name)
                        continue

                    co = ChromiumOptions()
                    co.set_address(f"127.0.0.1:{test_port}")
                    co.set_load_mode("eager")

                    browser = Chromium(addr_or_opts=co)
                    tab = browser.latest_tab

                    if tab:
                        self.local_port = test_port
                        self.browser = browser
                        logger.info("attached to %s via local port %d", sock.name, test_port)
                        return self.browser

                    logger.debug("no tab available via %s", sock.name)

                except Exception:
                    logger.exception("attach via %s failed", sock.name)
                finally:
                    # 未成功接管时，清理残留的驱动和端口映射，绝不让 forward 泄漏
                    if self.browser is None:
                        if browser is not None:
                            self._stop_browser_drivers(browser)
                        try:
                            device.forward_remove(f"tcp:{test_port}")
                        except Exception:
                            logger.debug("forward_remove tcp:%s failed", test_port, exc_info=True)

            time.sleep(0.2)

        raise RuntimeError(
            f"no healthy WebView devtools socket found" + (f" for package {target}" if target else "")
        )

    @property
    def current_page(self):
        """
        懒加载获取页面。
        如果在未 attach 的情况下访问该属性，会自动触发 attach 逻辑。
        会话失效时清理全部资源（含 adb 端口转发）后抛出原始异常，
        不再返回 None —— 避免错误在别处以 AttributeError 的形式出现。
        """
        if not self.browser:
            self.attach()
        try:
            return self.browser.latest_tab
        except Exception:
            logger.exception("failed to get current page; detaching stale session")
            self.detach()
            raise

    def detach(self):
        """断开 WebView 连接，释放驱动、DrissionPage 缓存与 adb 端口转发"""
        if self.browser is not None:
            try:
                self._stop_browser_drivers(self.browser)
            finally:
                self.browser = None

            # 清理 DrissionPage 底层的全局单例缓存字典
            try:
                if hasattr(_Chromium_Class, "_BROWSERS"):
                    _Chromium_Class._BROWSERS.clear()
                if hasattr(BrowserDriver, "BROWSERS"):
                    BrowserDriver.BROWSERS.clear()
            except Exception:
                logger.debug("error clearing DrissionPage caches", exc_info=True)

        if self.d and self.local_port:
            try:
                adb.device(serial=self.d.serial).forward_remove(f"tcp:{self.local_port}")
            except Exception:
                logger.debug("forward_remove tcp:%s failed", self.local_port, exc_info=True)
            finally:
                self.local_port = None
