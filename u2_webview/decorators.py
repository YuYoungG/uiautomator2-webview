# -*- coding: utf-8 -*-
import traceback
from functools import wraps


def with_webview(func):
    """
    H5 混合页面装饰器（懒连接）。

    不在方法体前强连（attach），连接由方法内首次访问
    ``self.webview.current_page`` 自动触发。这样支持「先原生点击控件
    进入 H5，再操作页面」的原生优先流程：入口用 native 前置条件把关，
    H5 就位则由 attach 的 socket 轮询兜底，无需依赖脆弱的 H5 元素判断。
    """

    @wraps(func)
    def wrapper(self, *args, **kwargs):
        try:
            return func(self, *args, **kwargs)

        except Exception as e:
            tb = e.__traceback__

            if tb is not None and tb.tb_next is not None:
                tb = tb.tb_next

            traceback.print_exception(type(e), e, tb)

        finally:
            if hasattr(self, "webview") and self.webview is not None:
                self.webview.detach()

    return wrapper
