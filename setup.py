# 文件：setup.py
from setuptools import setup, find_packages

setup(
    name="u2_webview",                      # 安装时包的名字：pip install u2_webview
    version="0.1.0",                        # 版本号
    description="An extension for uiautomator2 to support WebView automation via DrissionPage",
    author="Younggg",                 # 你的名字
    packages=find_packages(),               # 自动发现 u2_webview 文件夹
    install_requires=[                      # 这个包依赖的其他库
        "uiautomator2>=2.16.0",
        "DrissionPage>=4.1.0",
        "adbutils>=0.11.0"                  # 确保 adbutils 存在
    ],
    python_requires=">=3.8",
)