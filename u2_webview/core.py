# -*- coding:utf-8 -*-
import time
import re
import socket
import atexit
import traceback
from adbutils import adb
from DrissionPage import Chromium, ChromiumOptions

class Webview:
    """
    u2_webview 扩展类
    设计参考 Flask Extension 模式：支持预初始化和延迟绑定设备
    """
    def __init__(self, d=None):
        self.d = None
        self.browser = None
        self.local_port = None
        self._socket_name = None
        
        # 如果初始化时传入了设备，则直接绑定
        if d is not None:
            self.init_device(d)

    def init_device(self, d):
        """
        将扩展绑定到具体的 uiautomator2 Device 实例上
        """
        self.d = d
        # 自动获取一个当前实例专用的空闲端口
        self.local_port = self._get_free_port()
        
        # 注册进程退出时的清理
        atexit.register(self.detach)

    def _get_free_port(self):
        """获取本地空闲端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            return s.getsockname()[1]

    def _find_webview_socket(self, timeout=15):
        """侦测手机内 WebView 调试接口"""
        if not self.d:
            raise RuntimeError("扩展尚未绑定设备，请先调用 init_device(d)")
            
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # grep -a 处理二进制干扰
                output = self.d.shell("cat /proc/net/unix | grep -a devtools_remote").output.strip()
                if output:
                    lines = output.splitlines()
                    for line in reversed(lines):
                        match = re.search(r'webview_devtools_remote_\d+', line) or \
                                re.search(r'chrome_devtools_remote_\d+', line)
                        if match:
                            return match.group(0)
            except Exception:
                traceback.print_exc()
            time.sleep(0.5)
        return None

    def attach(self, timeout=20):
        """建立连接（核心行为）"""
        if self.browser:
            return self.browser

        if not self.d:
            raise RuntimeError("请先通过 Webview(d) 或 init_device(d) 绑定设备")

        socket_name = self._find_webview_socket(timeout=timeout)
        if not socket_name:
            raise RuntimeError("❌ 未检测到 WebView Socket，请确认 App 已进入 H5 页面并开启调试")

        # 建立 ADB 隧道
        try:
            device = adb.device(serial=self.d.serial)
            device.forward(f"tcp:{self.local_port}", f"localabstract:{socket_name}")
        except Exception:
            traceback.print_exc()

        # 连接 DrissionPage
        try:
            co = ChromiumOptions()
            co.set_address(f'127.0.0.1:{self.local_port}')
            self.browser = Chromium(addr_or_opts=co)
            return self.browser
        except Exception:
            traceback.print_exc()

    @property
    def current_page(self):
        """
        懒加载获取页面。
        如果在未 attach 的情况下访问该属性，会自动触发 attach 逻辑。
        """
        if not self.browser:
            self.attach()
        return self.browser.latest_tab

    def detach(self):
        """断开链接清理资源"""
        if self.browser:
            self.browser = None
        if self.d and self.local_port:
            try:
                device = adb.device(serial=self.d.serial)
                device.forward_remove(f"tcp:{self.local_port}")
            except Exception:
                traceback.print_exc()