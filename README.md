# u2_webview

**u2_webview** 是一个专为 `uiautomator2` 定制的混合应用（Hybrid App）自动化扩展库。它通过集成 `DrissionPage` ，实现了对移动端 WebView 的“无驱动”（Driverless）接管。

##  工具定位

在进行“Android 原生 + WebView H5”的混合应用自动化测试时，开发者通常会面临以下尴尬的割裂感：

- **`chrome://inspect/#devices` 类型工具的局限**：优秀的前端**手动调试**工具，但无法用于编写自动化脚本，更无法去操作 Android 的原生控件。
- **`uiautomator2` 的局限**：作为安卓自动化神器，它能操控所有原生 UI，但在面对内部嵌套的 WebView 页面时，无法精准提取和交互 HTML 元素。

**`u2_webview` 用来解决二者的局限。**
它让你在同一个 Python 自动化脚本中，既能用 `u2` 丝滑操作 Android 原生外壳，又能随时调用 `u2_webview` 穿透进入 H5 内部，真正实现“Android 原生 + WebView”混合应用的无缝自动化协同。

##  演示demo

https://github.com/user-attachments/assets/c80233fd-75cd-4ba4-a180-28c097f09a89


##  核心优势

- **免驱动接管 (Driverless)**：不同于传统的 Selenium/Appium，本库无需下载、配置或匹配特定版本的 `chromedriver`。它通过 CDP 协议直接与 WebView 通信，彻底告别驱动版本不匹配的烦恼。
- **Flask 扩展模式设计**：遵循 Flask 插件设计哲学，支持“应用工厂”模式，实现与 `uiautomator2.Device` 实例的完全解耦。
- **高性能通信**：基于 `adbutils` 建立高效的端口转发隧道，确保 H5 操作的高响应速度与稳定性。
- **API 极简**：只需一个属性 `.current_page`，即可像操作浏览器一样操作手机内的 H5 页面。
- **智能防代理劫持**：内置本地网络护盾，即使宿主机开启了 VPN 或全局代理（如 Clash），也能保证与手机 WebView 的本地通信直连不报错。

##  环境要求

- **Python**: 3.8 或更高版本
- **Android 设备**: 需开启 ADB 调试
- **被测 App**: WebView 必须开启调试模式（`setWebContentsDebuggingEnabled(true)`）

##  安装

通过 PyPI 直接安装最新稳定版：

```
pip install --upgrade u2_webview
```

或者从源码本地安装（开发模式）：

```
git clone [https://github.com/YuYoungG/uiautomator2-webview.git](https://github.com/YuYoungG/uiautomator2-webview.git)
cd uiautomator2-webview
pip install -e .
```

##  使用指南

本库支持两种初始化模式，以适配不同的框架架构。API 极其精简，只需一个属性 .current_page，即可像操作浏览器一样操作手机内的 H5 页面。

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

# 继续原生操作...
d(text="返回").click()
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

启动智能探针，扫描并建立与手机 WebView 的可用调试连接。成功后返回 `DrissionPage.Chromium` 对象。

### `webview.current_page` (Property)

**核心属性**。获取当前活跃的标签页对象（`ChromiumTab`）。

- *注：若未连接，访问此属性将自动调用 `attach()`并具有容错重试机制。*

### `webview.detach()`

**核心清理方法**。安全停用后台事件监听线程，清空框架对象缓存，并移除 ADB 端口转发隧道，彻底释放系统资源。

##  常见问题

**Q: u2_webview 和 Appium、Selenium 有何不同？有何优势？**

1. 免驱动 (Driverless)：Appium 与 Selenium 依赖 chromedriver，手机内核一升级脚本就容易因版本不匹配报错。本库基于 CDP 协议直连，永远不需要下载和匹配驱动，无视 WebView 版本更迭。

2. 轻量与速度：Appium 需要庞大的 Node.js 服务端和繁杂的环境配置（Java/Android SDK），通信链路长。本库是纯 Python 栈，局域网直连 WebSocket，执行速度更快。

3. 为“探索测试”而生：传统工具基于线性脚本思维，遇到异常容易直接崩溃。本库配合自带的 @with_webview 装饰器，契合非线性、高频次的探索测试，如与Kea2工具结合使用。

**Q: 为什么找不到 WebView Socket？**

1. 请确认 App 已经进入了包含 H5 的 Activity。
2. 请确认 App 源码中开启了 WebView 调试：`WebView.setWebContentsDebuggingEnabled(true);`。如果是第三方 App，可能需要使用 Xposed 模块（如 WebViewDebugHook）强制开启。

**Q: 是否支持多设备并行？**

支持。每个 `Webview` 实例在初始化时都会自动分配一个独立的本地空闲端口，多台手机同时运行不会发生冲突。

**Q: 为什么在多次切换 H5 时，其他库容易报错误，而 u2_webview 不会？**

这是 u2_webview 的核心竞争力。在底层实现了源码级的清理引擎，每次 `detach()` 都会强制停用残留的守护线程并清空单例缓存池，确保每一次重新 `attach()` 面对的都是一个健康、崭新的通信通道。

##  进阶用法：与Kea2框架结合

`u2_webview` 专门为基于性质测试的 Android 自动化测试工具 Kea2 提供了深度适配与语法糖。
Kea2仓库地址：https://github.com/ecnusse/Kea2

### 为什么需要 `@with_webview` 装饰器？

1.自动建连：在执行你的 H5 逻辑前，自动寻找底层活跃的 DevTools Socket 并建立连接 (attach)。

2.异常拦截与追踪：在探索过程中，如果因页面未加载完毕导致元素找不到，装饰器会完美拦截异常，打印 traceback 堆栈。

3.安全断连：无论代码执行成功还是抛出异常，都会在最后一步强制清理底层的 Socket 隧道和守护线程 (detach)，保证下一次探索的纯净环境。

### Kea2 混合自动化测试示例

将 `@with_webview` 与 Kea2 的 `@precondition` 和 `@prob` 组合使用，你的代码将变得职责分明、极其干净。

```
import random
import unittest
import uiautomator2 as u2
from kea2 import precondition, prob, max_tries
# 引入 u2_webview 核心组件与装饰器
from u2_webview import Webview, with_webview

class HybridAppTest(unittest.TestCase):
    d: u2.Device

    @classmethod
    def setUpClass(cls):
        cls.d.settings["wait_timeout"] = 5.0
        cls.d.app_clear("com.example.app")
        cls.webview = Webview(cls.d)

    # ================= 状态流转：处理 H5 弹窗 =================
    @prob(0.8) 
    @precondition(
        lambda self: self.d(text="Slide to complete the puzzle").exists
    )
    @with_webview  # 🌟 挂载装饰器，自动接管 H5 生命周期
    def test_geetest_h5_handler(self):
        print("💡 发现 WebView 容器，开始自动接管...")
        # 直接获取current_page即可
        tab = self.webview.current_page
        print(f"🌐 当前标题: {tab.title}")

        # 拖拽滑块示例
        slider = tab.ele('.geetest_slider_button')
        if slider:
            tab.actions.hold(slider).move(200, 0, duration=random.uniform(0.8, 1.2)).release()
            print("✅ 滑块拖拽完成")

        # 关闭弹窗
        if tab.ele('.geetest_close'):
            tab.ele('.geetest_close').click()
            print("✅ H5 弹窗已关闭")
```

##  开源协议

本项目采用 [MIT License](https://opensource.org/licenses/MIT) 协议。

**贡献与支持**: 欢迎提交 Issue 或 Pull Request 来完善本项目！如果这个项目帮助到了你，欢迎点亮 ⭐️ Star！
