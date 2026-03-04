# u2_webview

**u2_webview** 是一个专为 `uiautomator2` 定制的混合应用（Hybrid App）自动化扩展库。它通过集成 `DrissionPage` ，实现了对移动端 WebView 的“无驱动”（Driverless）接管。

##  核心优势

- **免驱动接管 (Driverless)**：不同于传统的 Selenium/Appium，本库无需下载、配置或匹配特定版本的 `chromedriver`。它通过 CDP 协议直接与 WebView 通信，彻底告别驱动版本不匹配的烦恼。
- **Flask 扩展模式设计**：遵循 Flask 插件设计哲学，支持“应用工厂”模式，实现与 `uiautomator2.Device` 实例的完全解耦。
- **高性能通信**：基于 `adbutils` 建立高效的端口转发隧道，确保 H5 操作的高响应速度与稳定性。
- **API 极简**：只需一个属性 `.current_page`，即可像操作浏览器一样操作手机内的 H5 页面。

##  环境要求

- **Python**: 3.8 或更高版本
- **Android 设备**: 需开启 ADB 调试
- **被测 App**: WebView 必须开启调试模式（`setWebContentsDebuggingEnabled(true)`）

##  安装

通过 PyPI 直接安装：

```
pip install u2_webview
```

或者从源码本地安装（开发模式）：

```
git clone [https://github.com/YuYoungG/uiautomator2-webview.git](https://github.com/YuYoungG/uiautomator2-webview.git)
cd uiautomator2-webview
pip install -e .
```

##  使用指南

本库支持两种初始化模式，以适配不同的框架架构。

### 1. 基础用法 (直接绑定)

适用于简单的脚本测试。

```
import uiautomator2 as u2
from u2_webview import Webview

# 连接设备
d = u2.connect()

# 实例化扩展并绑定设备
webview = Webview(d)

# 访问 H5 页面属性 (会自动触发 attach)
print(f"当前 H5 标题: {webview.current_page.title}")

# 使用 DrissionPage 语法进行操作
webview.current_page.ele('text:登录').click()

# 测试结束，清理资源
webview.detach()
```

### 2. 工厂模式用法 (推荐用于大型框架)

类似于 Flask 的 `init_app` 模式，适合在设备对象尚未完全确定时预定义扩展。

```
from u2_webview import Webview
import uiautomator2 as u2

# 全局预定义扩展对象
webview = Webview()

def run_test(serial):
    d = u2.connect(serial)
    
    # 在运行时绑定具体设备
    webview.init_device(d)
    
    # 接管并操作
    page = webview.current_page
    page.actions.move_to('.slider').click()
    
    webview.detach()
```

##  核心 API 参考

### `Webview(d=None)`

构造函数。可选参数 `d` 为 `uiautomator2.connect()` 返回的对象。

### `webview.init_device(d)`

将扩展实例绑定到特定的 `uiautomator2` 设备对象。

### `webview.attach(timeout=20)`

手动建立与手机 WebView 的调试连接。成功后返回 `DrissionPage.Chromium` 对象。

### `webview.current_page` (Property)

**核心属性**。获取当前活跃的标签页对象（`ChromiumTab`）。

- *注：若未连接，访问此属性将自动调用 `attach()`。*

### `webview.detach()`

断开 CDP 连接并移除 ADB 端口转发映射，释放系统资源。

##  常见问题

**Q: 为什么找不到 WebView Socket？**

1. 请确认 App 已经进入了包含 H5 的 Activity。
2. 请确认 App 源码中开启了 WebView 调试：`WebView.setWebContentsDebuggingEnabled(true);`。如果是第三方 App，可能需要使用 Xposed 模块（如 WebViewDebugHook）强制开启。

**Q: 是否支持多设备并行？** 支持。每个 `Webview` 实例在初始化时都会自动分配一个独立的本地空闲端口，多台手机同时运行不会发生冲突。

##  开源协议

本项目采用 [MIT License](https://opensource.org/licenses/MIT) 协议。

**贡献与支持**: 欢迎提交 Issue 或 Pull Request 来完善本项目。