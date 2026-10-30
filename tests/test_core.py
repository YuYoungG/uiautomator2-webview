# -*- coding: utf-8 -*-
"""u2_webview core 单元测试：socket 发现/解析/包名过滤/资源清理，全部不依赖真机。"""
import pytest

from u2_webview import core
from u2_webview.core import DevtoolsSocket, Webview, parse_unix_socket_lines


class FakeShellOutput:
    def __init__(self, text):
        self.output = text


class FakeDevice:
    """模拟 uiautomator2.Device：只实现 core.py 用到的 shell / serial。"""

    def __init__(self, unix_lines=(), cmdlines=None, serial="FAKE001"):
        self.serial = serial
        self._cmdlines = cmdlines or {}
        self._unix_text = "\n".join(unix_lines)

    def shell(self, cmd):
        if "cat /proc/net/unix" in cmd:
            return FakeShellOutput(self._unix_text)
        if cmd.startswith("cat /proc/") and cmd.endswith("/cmdline"):
            pid = int(cmd.split("/")[2])  # "cat /proc/<pid>/cmdline" -> 第 3 段是 pid
            return FakeShellOutput(self._cmdlines.get(pid, ""))
        raise AssertionError(f"unexpected shell command: {cmd}")


class FakeAdbDevice:
    """记录 forward 操作，用于断言无端口转发泄漏。"""

    def __init__(self):
        self.forwards = {}

    def forward(self, local, remote):
        self.forwards[local] = remote

    def forward_remove(self, local):
        self.forwards.pop(local, None)


class FakeTab:
    def __init__(self, url="about:blank"):
        self.url = url


class FakeChromium:
    def __init__(self, addr_or_opts=None):
        self.opts = addr_or_opts
        self.driver_stopped = False
        self._driver = self  # 模拟 DrissionPage 内部驱动句柄

    @property
    def latest_tab(self):
        return FakeTab()

    def stop(self):
        self.driver_stopped = True


class ExplodingChromium(FakeChromium):
    @property
    def latest_tab(self):
        raise RuntimeError("boom")


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr(core.time, "sleep", lambda *_: None)


# ---------- parse_unix_socket_lines ----------

UNIX_SAMPLE = [
    "ffff8a8b 00000002 00000000 00010000 0001 01 12345 @webview_devtools_remote_111",
    "ffff8a8c 00000002 00000000 00010000 0001 01 12346 @com.example.shop_devtools_remote_222",
    "ffff8a8d 00000002 00000000 00010000 0001 01 12347 @chrome_devtools_remote",
    "ffff8a8e 00000002 00000000 00010000 0001 01 12348 /dev/socket/mdns",
]


def test_parse_resolves_package_from_pid():
    result = parse_unix_socket_lines(
        UNIX_SAMPLE[:1], resolve_package=lambda pid: f"com.app{pid}"
    )
    assert len(result) == 1
    sock = result[0]
    assert sock.name == "webview_devtools_remote_111"
    assert sock.pid == 111
    assert sock.package == "com.app111"


def test_parse_embedded_package_prefix_wins():
    result = parse_unix_socket_lines(UNIX_SAMPLE[1:2])
    assert result[0].package == "com.example.shop"
    assert result[0].pid == 222


def test_parse_chrome_browser_socket_without_pid():
    result = parse_unix_socket_lines(UNIX_SAMPLE[2:3])
    assert result[0].name == "chrome_devtools_remote"
    assert result[0].pid is None
    assert result[0].package is None


def test_parse_ignores_non_devtools_lines():
    assert parse_unix_socket_lines([UNIX_SAMPLE[3], "garbage line"]) == []


def test_parse_dedupes_repeated_entries():
    lines = [UNIX_SAMPLE[0], UNIX_SAMPLE[0]]
    assert len(parse_unix_socket_lines(lines)) == 1


def test_parse_latest_socket_first():
    result = parse_unix_socket_lines(UNIX_SAMPLE[:2])
    assert result[0].pid == 222
    assert result[1].pid == 111


# ---------- DevtoolsSocket.matches ----------

def test_matches_no_filter_keeps_all():
    sock = DevtoolsSocket(name="x", pid=None, package=None)
    assert sock.matches(None) and sock.matches("")


def test_matches_package_filter():
    known = DevtoolsSocket(name="a", pid=1, package="com.a")
    unknown = DevtoolsSocket(name="b", pid=2, package=None)
    assert known.matches("com.a")
    assert not known.matches("com.b")
    assert not unknown.matches("com.a")


# ---------- Webview discovery ----------

def test_list_devsockets_with_fake_device():
    d = FakeDevice(
        unix_lines=UNIX_SAMPLE,
        cmdlines={111: "com.target.app"},
    )
    sockets = Webview(d).list_devsockets()
    # 反转后最新创建的排最前：chrome(None) -> shop -> target
    assert [s.package for s in sockets] == [None, "com.example.shop", "com.target.app"]


def test_get_active_sockets_backward_compat():
    d = FakeDevice(unix_lines=UNIX_SAMPLE[:1])
    assert Webview(d)._get_active_sockets() == ["webview_devtools_remote_111"]


def test_attach_filters_by_package(monkeypatch, no_sleep):
    d = FakeDevice(
        unix_lines=UNIX_SAMPLE,
        cmdlines={111: "com.target.app", 222: "com.example.shop"},
    )
    adb_device = FakeAdbDevice()
    created = []

    def fake_chromium(addr_or_opts=None):
        browser = FakeChromium(addr_or_opts)
        created.append(browser)
        return browser

    monkeypatch.setattr(core.adb, "device", lambda serial: adb_device)
    monkeypatch.setattr(core, "Chromium", fake_chromium)
    monkeypatch.setattr(core, "probe_devtools_endpoint", lambda port, timeout=2.0: True)

    w = Webview(d, package="com.target.app")
    w.attach()

    # 只应向目标包的 socket（pid 111）建过转发
    assert adb_device.forwards == {"tcp:%d" % w.local_port: "localabstract:webview_devtools_remote_111"}
    assert len(created) == 1


def test_attach_timeout_when_package_socket_missing(monkeypatch, no_sleep):
    d = FakeDevice(unix_lines=UNIX_SAMPLE, cmdlines={111: "com.other", 222: "com.other2"})
    monkeypatch.setattr(core.adb, "device", lambda serial: FakeAdbDevice())
    monkeypatch.setattr(core, "probe_devtools_endpoint", lambda port, timeout=2.0: True)

    w = Webview(d, package="com.target.app")
    # 真实时钟 + 极短 timeout：目标包的 socket 永远不出现，循环耗尽后报错
    with pytest.raises(RuntimeError, match="com.target.app"):
        w.attach(timeout=0.01)


def test_attach_dead_socket_no_forward_leak(monkeypatch, no_sleep):
    d = FakeDevice(unix_lines=UNIX_SAMPLE, cmdlines={111: "com.target.app", 222: "com.target.app"})
    adb_device = FakeAdbDevice()
    monkeypatch.setattr(core.adb, "device", lambda serial: adb_device)
    monkeypatch.setattr(core, "probe_devtools_endpoint", lambda port, timeout=2.0: False)

    w = Webview(d)
    with pytest.raises(RuntimeError):
        w.attach(timeout=0.01)

    # 所有候选都探活失败：不留任何端口转发
    assert adb_device.forwards == {}
    assert w.local_port is None
    assert w.browser is None


def test_attach_chromium_failure_cleans_up(monkeypatch, no_sleep):
    d = FakeDevice(unix_lines=UNIX_SAMPLE, cmdlines={111: "com.target.app"})
    adb_device = FakeAdbDevice()
    monkeypatch.setattr(core.adb, "device", lambda serial: adb_device)

    created = []

    def fake_chromium(addr_or_opts=None):
        browser = ExplodingChromium(addr_or_opts)
        created.append(browser)
        return browser

    monkeypatch.setattr(core, "Chromium", fake_chromium)
    monkeypatch.setattr(core, "probe_devtools_endpoint", lambda port, timeout=2.0: True)

    w = Webview(d)
    with pytest.raises(RuntimeError):
        w.attach(timeout=0.01)

    assert created and created[0].driver_stopped  # 失败实例的驱动被停止
    assert adb_device.forwards == {}
    assert w.local_port is None


def test_current_page_failure_detaches_and_raises(monkeypatch, no_sleep):
    d = FakeDevice(unix_lines=UNIX_SAMPLE, cmdlines={111: "com.target.app"})
    adb_device = FakeAdbDevice()
    monkeypatch.setattr(core.adb, "device", lambda serial: adb_device)
    monkeypatch.setattr(core, "Chromium", FakeChromium)
    monkeypatch.setattr(core, "probe_devtools_endpoint", lambda port, timeout=2.0: True)

    w = Webview(d, package="com.target.app")
    browser = w.attach()

    # 会话中途失效
    monkeypatch.setattr(type(browser), "latest_tab",
                        property(lambda self: (_ for _ in ()).throw(RuntimeError("stale"))))

    with pytest.raises(RuntimeError, match="stale"):
        w.current_page

    # 完整清理：驱动停止 + 转发移除 + 状态复位
    assert browser.driver_stopped
    assert adb_device.forwards == {}
    assert w.local_port is None
    assert w.browser is None


def test_attach_without_device_raises():
    with pytest.raises(RuntimeError, match="device not bound"):
        Webview().attach(timeout=0.01)
