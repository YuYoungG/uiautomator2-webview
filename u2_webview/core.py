# -*- coding:utf-8 -*-
import time
import re
import socket
import atexit
import os
import traceback
from adbutils import adb
from DrissionPage import Chromium, ChromiumOptions
from DrissionPage._base.chromium import Chromium as _Chromium_Class
from DrissionPage._base.driver import BrowserDriver

os.environ['NO_PROXY'] = '127.0.0.1,localhost'

class Webview:
    def __init__(self, d=None):
        self.d = d
        self.browser = None
        self.local_port = None

    def init_device(self, d):
        self.d = d
        atexit.register(self.detach)

    def _get_free_port(self):
        """让操作系统自动分配一个可用的空闲端口"""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('127.0.0.1', 0))
            return s.getsockname()[1]

    def _get_active_sockets(self):
        output = self.d.shell("cat /proc/net/unix | grep -a devtools_remote").output.strip()
        sockets = []
        if output:
            lines = output.splitlines()
            for line in lines:
                match = re.search(r'webview_devtools_remote_\d+', line) or \
                        re.search(r'chrome_devtools_remote_\d+', line)
                if match:
                    sock = match.group(0)
                    if sock not in sockets:
                        sockets.append(sock)
        return list(reversed(sockets))

    def attach(self, timeout=20):
        """建立连接（核心行为）"""
        if self.browser: 
            return self.browser
        
        device = adb.device(serial=self.d.serial)
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            candidate_sockets = self._get_active_sockets()
            
            for sock in candidate_sockets:
                test_port = self._get_free_port()
                
                try: device.forward_remove(f"tcp:{test_port}")
                except: pass
                
                try:
                    device.forward(f"tcp:{test_port}", f"localabstract:{sock}")
                    
                    co = ChromiumOptions()
                    co.set_address(f'127.0.0.1:{test_port}')
                    co.set_load_mode('eager') 
                    
                    browser = Chromium(addr_or_opts=co)
                    tab = browser.latest_tab 
                    
                    if tab:
                        self.local_port = test_port
                        self.browser = browser
                        return self.browser
                        
                except Exception:
                    traceback.print_exc()
                    # 探测失败，清理残留的驱动和端口映射
                    if 'browser' in locals() and browser:
                        if hasattr(browser, '_driver') and browser._driver:
                            browser._driver.stop()
                    device.forward_remove(f"tcp:{test_port}")
                    continue 
            
        raise RuntimeError("未找到健康活跃的 WebView Socket")

    @property
    def current_page(self):
        """
        懒加载获取页面。
        如果在未 attach 的情况下访问该属性，会自动触发 attach 逻辑。
        """
        if not self.browser: self.attach()
        try:
            return self.browser.latest_tab
        except Exception:
            traceback.print_exc()
            self.browser = None

    def detach(self):
        """断开 WebView 连接"""
        if self.browser:
            try:
                # 精准击杀所有 Tab 的驱动
                if hasattr(self.browser, '_all_drivers'):
                    for driver_set in list(self.browser._all_drivers.values()):
                        for d in driver_set:
                            if hasattr(d, 'stop'):
                                d.stop()

                # 精准击杀主驱动
                if hasattr(self.browser, '_driver') and self.browser._driver:
                    self.browser._driver.stop() 
                
                # 强制清理 DrissionPage 底层的全局单例缓存字典
                if hasattr(_Chromium_Class, '_BROWSERS'):
                    _Chromium_Class._BROWSERS.clear()
                if hasattr(BrowserDriver, 'BROWSERS'):
                    BrowserDriver.BROWSERS.clear()
            except Exception:
                traceback.print_exc()
            finally:
                self.browser = None
        
        if self.d and self.local_port:
            try:
                adb.device(serial=self.d.serial).forward_remove(f"tcp:{self.local_port}")
            except Exception:
                traceback.print_exc()
            finally:
                self.local_port = None