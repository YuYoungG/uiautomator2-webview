# u2_webview

<p align="center">
  <a href="./README.md"><strong>English</strong></a> · <a href="./README_CN.md">简体中文</a>
</p>

**u2_webview** is a hybrid app automation extension library designed for `uiautomator2`. By integrating `DrissionPage`, it provides a driverless way to take control of mobile WebView pages.

## What It Is For

When automating hybrid apps with both Android native UI and WebView H5 content, developers often run into a frustrating split:

- **Limitations of tools like `chrome://inspect/#devices`**: great for manual front-end debugging, but not for writing automation scripts or interacting with Android native controls.
- **Limitations of `uiautomator2`**: excellent for native Android UI, but not precise enough for extracting and interacting with HTML elements inside embedded WebView pages.

**`u2_webview` is built to bridge that gap.**
It lets you use `u2` to operate the Android native shell smoothly in the same Python script, while switching into `u2_webview` whenever you need to step into the H5 layer and achieve seamless hybrid app automation.

## Demo

https://github.com/user-attachments/assets/c80233fd-75cd-4ba4-a180-28c097f09a89

## Key Features

- **Driverless takeover**: unlike traditional Selenium/Appium workflows, this library does not require you to download, configure, or match a specific `chromedriver` version. It connects to WebView directly through the CDP protocol, eliminating driver mismatch issues.
- **Flask-style extension design**: follows the Flask plugin philosophy and supports an application-factory pattern, fully decoupled from the `uiautomator2.Device` instance.
- **High-performance communication**: uses `adbutils` to build efficient port-forwarding tunnels for responsive and stable H5 interactions.
- **Minimal API**: a single property, `.current_page`, is enough to operate a mobile H5 page like a browser tab.
- **Smart proxy protection**: built-in local network shielding ensures local communication with the phone WebView stays direct and error-free, even when the host machine is using a VPN or a system-wide proxy such as Clash.

## Requirements

- **Python**: 3.8 or later
- **Android device**: ADB debugging must be enabled
- **App under test**: WebView debugging must be enabled (`setWebContentsDebuggingEnabled(true)`)

## Installation

Install the latest stable release from PyPI:

```bash
pip install --upgrade u2_webview
```

Or install from source in development mode:

```bash
git clone https://github.com/YuYoungG/uiautomator2-webview.git
cd uiautomator2-webview
pip install -e .
```

## Usage

This library supports two initialization styles to fit different framework architectures. The API is intentionally small: with a single `.current_page` property, you can operate H5 content inside the phone just like a browser.

### 1. Basic usage (direct binding)

Suitable for simple scripts.

```python
import uiautomator2 as u2
from u2_webview import Webview

# Connect to device
d = u2.connect()

# Create the extension and bind the device
webview = Webview(d)

# Access H5 page properties (this will trigger attach automatically)
print(f"Current H5 title: {webview.current_page.title}")

# Interact with the page using DrissionPage syntax
webview.current_page.ele('text:Login').click()

# Clean up resources when finished
webview.detach()

# Continue native automation...
d(text="Back").click()
```

### 2. Factory-style usage (recommended for larger frameworks)

Similar to Flask's `init_app` pattern, this is useful when the device object is not known until runtime.

```python
from u2_webview import Webview
import uiautomator2 as u2

# Predefine the extension globally
webview = Webview()

def run_test(serial):
    d = u2.connect(serial)

    # Bind the concrete device at runtime
    webview.init_device(d)

    # Take over and operate the page
    page = webview.current_page
    page.actions.move_to('.slider').click()

    webview.detach()
```

## Core API Reference

### `Webview(d=None)`

Constructor. Optional `d` is the object returned by `uiautomator2.connect()`.

### `webview.init_device(d)`

Bind the extension instance to a specific `uiautomator2` device object.

### `webview.attach(timeout=20)`

Start the smart probe, scan for an available WebView debug connection, and establish the connection. Returns a `DrissionPage.Chromium` object on success.

### `webview.current_page` (property)

**Core property**. Returns the currently active tab object (`ChromiumTab`).

- Note: if the extension is not connected yet, accessing this property will automatically call `attach()` with retry handling.

### `webview.detach()`

**Core cleanup method**. Safely stops the background event-listening thread, clears framework caches, and removes the ADB port-forwarding tunnel to release all system resources.

## FAQ

**Q: How is u2_webview different from Appium or Selenium? What are the advantages?**

1. Driverless: Appium and Selenium rely on `chromedriver`, and scripts often break when the phone kernel or WebView version changes. This library connects directly through CDP, so there is no need to download or match a driver.
2. Lightweight and fast: Appium requires a heavy Node.js server and a more complicated environment (Java / Android SDK), which adds extra hops. This library is pure Python and communicates directly over a local WebSocket, so it runs faster.
3. Built for exploratory testing: traditional tools are based on linear script thinking and can fail hard when something unexpected happens. This library works well with the built-in `@with_webview` decorator and fits non-linear, high-frequency exploratory testing, especially when combined with Kea2.

**Q: Why can't I find the WebView socket?**

1. Make sure the app has already entered an Activity that contains H5 content.
2. Make sure WebView debugging is enabled in the app source: `WebView.setWebContentsDebuggingEnabled(true);`. For third-party apps, you may need an Xposed module such as WebViewDebugHook to force it on.

**Q: Does it support multi-device parallel execution?**

Yes. Each `Webview` instance automatically allocates a separate free local port during initialization, so multiple phones can run at the same time without conflicts.

**Q: Why do other libraries often fail after switching H5 pages multiple times, while u2_webview does not?**

That is one of `u2_webview`'s core strengths. It includes a source-level cleanup engine underneath: every `detach()` forcefully shuts down leftover daemon threads and clears singleton caches, ensuring that every new `attach()` starts with a healthy and fresh communication channel.

## Advanced Usage: Integration with Kea2

`u2_webview` provides deep adaptation and syntax sugar for Kea2, an Android automation tool based on property-based testing.
Kea2 repository: https://github.com/ecnusse/Kea2

### Why do we need the `@with_webview` decorator?

1. Lazy auto-connect: the connection (`attach`) is not forced before the method body runs. It is triggered by the first access to `self.webview.current_page`, which polls for the active DevTools socket and establishes the connection. This supports the "native-first" flow: click a native control to enter the H5 page, then operate on it.
2. Exception interception and tracing: during exploration, if an element cannot be found because the page has not finished loading, the decorator cleanly intercepts the exception and prints the traceback.
3. Safe disconnect: whether the code succeeds or raises an exception, it always cleans up the socket tunnel and daemon threads (`detach`) at the end to keep the environment clean for the next exploration.

### Example: hybrid automation with Kea2

By combining `@with_webview` with Kea2's `@precondition` and `@prob`, your code becomes clearer and more maintainable.

```python
import random
import unittest
import uiautomator2 as u2
from kea2 import precondition, prob, max_tries
# Import the core components and decorator from u2_webview
from u2_webview import Webview, with_webview

class HybridAppTest(unittest.TestCase):
    d: u2.Device

    @classmethod
    def setUpClass(cls):
        cls.d.settings["wait_timeout"] = 5.0
        cls.d.app_clear("com.example.app")
        cls.webview = Webview(cls.d)

    # ================= State transition: handle an H5 popup =================
    @prob(0.8)
    @precondition(
        lambda self: self.d(text="Slide to complete the puzzle").exists
    )
    @with_webview  # 🌟 Attach the decorator and take over the H5 lifecycle automatically
    def test_geetest_h5_handler(self):
        print("💡 WebView container found, starting takeover...")
        # Just access current_page directly
        tab = self.webview.current_page
        print(f"🌐 Current title: {tab.title}")

        # Slider drag example
        slider = tab.ele('.geetest_slider_button')
        if slider:
            tab.actions.hold(slider).move(200, 0, duration=random.uniform(0.8, 1.2)).release()
            print("✅ Slider dragged successfully")

        # Close popup
        if tab.ele('.geetest_close'):
            tab.ele('.geetest_close').click()
            print("✅ H5 popup closed")
```

## License

This project is licensed under the [MIT License](https://opensource.org/licenses/MIT).

**Contributions and support**: issues and pull requests are welcome. If this project helps you, please consider giving it a ⭐️ Star!
