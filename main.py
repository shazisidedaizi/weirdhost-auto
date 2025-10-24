#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import asyncio
import aiohttp
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

DEFAULT_SERVER_URL = "https://hub.weirdhost.xyz/server/d341874c"

# ------------------ Telegram 通知函数 ------------------
async def tg_notify(message: str):
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过 Telegram 通知")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, data={"chat_id": chat_id, "text": message})
        except Exception as e:
            print("⚠️ 发送 Telegram 消息失败:", e)

# ------------------ 主逻辑 ------------------
async def add_server_time():
    server_url = os.environ.get("SERVER_URL", DEFAULT_SERVER_URL)
    email = os.environ.get("PTERODACTYL_EMAIL")
    password = os.environ.get("PTERODACTYL_PASSWORD")

    if not email or not password:
        msg = "❌ 请设置环境变量 PTERODACTYL_EMAIL 与 PTERODACTYL_PASSWORD 后再运行。"
        print(msg)
        await tg_notify(msg)
        return

    print("🚀 启动 Playwright（Chromium），准备登录...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        try:
            # 打开登录页
            login_url = "https://hub.weirdhost.xyz/auth/login"
            await page.goto(login_url, timeout=60000)

            # 填写表单并登录
            await page.fill('input[name="email"]', email)
            await page.fill('input[name="password"]', password)
            await page.click('button[type="submit"]')

            try:
                await page.wait_for_url("**/server/**", timeout=20000)
            except PlaywrightTimeoutError:
                await page.wait_for_load_state("networkidle", timeout=10000)

            # 访问服务器页面
            await page.goto(server_url, timeout=30000)
            await page.wait_for_load_state("networkidle")

            # 查找按钮
            add_button = page.locator('button:has-text("시간 추가")')
            if await add_button.count() == 0:
                add_button = page.locator('text=시간 추가')
            if await add_button.count() == 0:
                add_button = page.locator('button:has-text("Add Time")')

            if await add_button.count() == 0:
                await page.screenshot(path="no_button_found.png", full_page=True)
                msg = "❌ 未找到 '시간 추가' 按钮，已保存 no_button_found.png"
                print(msg)
                await tg_notify(msg)
                return

            # 点击按钮
            await add_button.nth(0).click()
            await page.wait_for_timeout(3000)

            msg = f"✅ 续期操作已完成：{server_url}"
            print(msg)
            await tg_notify(msg)

        except Exception as e:
            msg = f"❌ 脚本异常: {repr(e)}"
            print(msg)
            try:
                await page.screenshot(path="error_screenshot.png", full_page=True)
                print("📸 已保存错误截图：error_screenshot.png")
            except Exception as se:
                print("⚠️ 无法保存截图：", se)
            await tg_notify(msg)

        finally:
            await context.close()
            await browser.close()


if __name__ == "__main__":
    asyncio.run(add_server_time())
