# -*- coding: utf-8 -*-
"""
u2_webview 验证脚本：bilimiao App 原生与 H5 混合操作演示
"""
import uiautomator2 as u2
import time
import random
from u2_webview import Webview

# ================= 配置区域 =================
PACKAGE_NAME = "com.a10miaomiao.bilimiao"  # 被测 App 包名


def main():
    print("🚀 开始验证: u2_webview + bilimiao 混合自动化测试...")
    
    # 1. 连接设备
    try:
        d = u2.connect()
        print(f"📱 设备已连接: {d.serial}")
    except Exception as e:
        print(f"❌ 设备连接失败，请检查 ADB 连接: {e}")
        return

    print("\n--- 🎬 演示开始 ---")
    try:
        # ==========================================
        # 2. [原生阶段] 启动与导航
        # ==========================================
        print(f"▶️ [Native] 启动 App: {PACKAGE_NAME}")
        d.app_start(PACKAGE_NAME, stop=True)
        time.sleep(2)  # 等待冷启动

        print("👆 [Native] 执行登录前置操作...")
        # 点击初始入口
        d(className="android.widget.LinearLayout", clickable=True).click()
        time.sleep(2)
        
        # 点击进入登录页面
        d(text="点这里可以登录喵！").click()
        time.sleep(2)
        
        # 选择手机号登录
        d(text="手机号登录").click()
        time.sleep(2)
        
        # 输入测试手机号
        d(className="android.widget.EditText").set_text("13574884105")
        time.sleep(1)
        
        # 点击获取验证码，触发极验 (Geetest) H5 弹窗
        print("🖱️ [Native] 点击获取验证码，准备触发 H5...")
        d(text="获取验证码").click()
        time.sleep(5)  # 等待 WebView 加载完全

        # ==========================================
        # 3. [H5 阶段] 使用 Webview 扩展接管操作
        # ==========================================
        print("\n🌐 [Webview] 正在初始化扩展并接管 H5...")
        # 实例化扩展对象
        webview = Webview(d)
        
        # 自动探测 Socket 并建立 CDP 连接
        # 调用 current_page 会触发自动 attach()
        tab = webview.current_page
        
        print(f"✅ [Webview] 已进入 H5 环境")
        print(f"🌐 页面标题: {tab.title}")
        print(f"🔗 页面 URL: {tab.url}")

        # --- 执行极验交互 ---
        
        # 3.1 点击刷新按钮
        if tab.ele('.geetest_refresh_1'):
            print("   -> 点击刷新按钮")
            tab.ele('.geetest_refresh_1').click()
            time.sleep(2)
        else:
            print("   ⚠️ 未找到刷新按钮")

        # 3.2 模拟滑动滑块
        print("   -> 正在模拟滑动滑块 (.geetest_slider_button)...")
        slider = tab.ele('.geetest_slider_button')
        if slider:
            # 模拟人的拖拽行为，带随机持续时间
            tab.actions.hold(slider).move(200, 0, duration=random.uniform(0.8, 1.2)).release()
            print("   ✅ 滑动完成")
            time.sleep(2)
        else:
            print("   ⚠️ 未找到滑块按钮")

        # 3.3 点击关闭按钮退出 H5
        if tab.ele('.geetest_close'):
            print("   -> 点击关闭按钮退出验证")
            tab.ele('.geetest_close').click()
            time.sleep(1)
        else:
            print("   ⚠️ 未找到关闭按钮")

        # ==========================================
        # 4. [资源释放] 断开 Webview 连接
        # ==========================================
        print("\n🔄 [Cleanup] 执行 Detach，交还控制权...")
        webview.detach()
        print("✅ 资源清理完成")

        # ==========================================
        # 5. [回归原生] 继续剩余操作
        # ==========================================
        print("\n👆 [Native] 回归原生环境，继续后续操作...")
        
        # 验证是否可以再次输入
        print("   -> 修改手机号输入框内容...")
        d(className="android.widget.EditText").set_text("13574880558")
        time.sleep(1)
        
        # 继续点击原生 Layout
        d(className="android.widget.LinearLayout", clickable=True).click()
        time.sleep(2)

    except Exception as e:
        print(f"\n❌ 运行时发生错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n🎉 演示结束！成功完成 Hybrid 应用的全流程切换验证。")

if __name__ == "__main__":
    main()