# -*- coding: utf-8 -*-
import traceback
from functools import wraps

def with_webview(func):
    """
    H5 混合页面装饰器
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            self.webview.attach()
            return func(self, *args, **kwargs)
            
        except Exception as e:
            tb = e.__traceback__
            
            if tb is not None and tb.tb_next is not None:
                tb = tb.tb_next
                
            traceback.print_exception(type(e), e, tb)
            
        finally:
            if hasattr(self, 'webview') and self.webview is not None:
                self.webview.detach()
                
    return wrapper