# 文件：setup.py
from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="u2_webview",
    version="0.1.0",
    description="An extension for uiautomator2 to support WebView automation via DrissionPage",
    author="YuYoungG",
    author_email="younggg2218@gmail.com",
    packages=find_packages(),
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/YuYoungG/uiautomator2-webview",
    install_requires=[                      # 依赖的其他库
        "uiautomator2>=2.16.0",
        "DrissionPage>=4.1.0",
        "adbutils>=0.11.0"
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
)