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
        print("⚠️ TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过 Telegram 消息")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    async with aiohttp.ClientSession() as session:
        try:
            await session.post(url, data={"chat_id": chat_id, "text": message})
        except Exception as e:
            print("⚠️ 发送 Telegram 消息失败:", e)

async def tg_notify_photo(photo_path: str, caption: str = ""):
    token = os.environ.get("TG_BOT_TOKEN")
    chat_id = os.environ.get("TG_CHAT_ID")
    if not token or not chat_id:
        print("⚠️ TG_BOT_TOKEN 或 TG_CHAT_ID 未设置，跳过 Telegram 图片通知")
        return
    url = f"https://api.telegram.org/bot{token}/sendPhoto"
    async with aiohttp.ClientSession() as session:
        try:
            with open(photo_path, "rb") as f:
                data = aiohttp.FormData()
                data.add_field("chat_id", chat_id)
                data.add_field("photo", f, filename=os.path.basename(photo_path))
                if caption:
                    data.add_field("caption", caption)
                await session.post(url, data=data)
        except Exception as e:
            print("⚠️ 发送 Telegram 图片失败:", e)

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

        # 设置全局 timeout
        page.set_default_timeout(120000)
        page.set_default_navigation_timeout(120000)

        try:
            # ------------------ 登录 ------------------
            login_url = "https://hub.weirdhost.xyz/auth/login"
            await page.goto(login_url, timeout=120000)

            await page.wait_for_selector('input', timeout=60000)
            inputs = await page.query_selector_all('input')

            if len(inputs) < 2:
                screenshot_path = "login_inputs_not_found.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                msg = "❌ 登录页面输入框不足两个，无法填写邮箱和密码"
                print(msg)
                await tg_notify_photo(screenshot_path, caption=msg)
                await tg_notify(msg)
                return

            # 填写邮箱和密码
            await inputs[0].fill(email, timeout=120000)
            await inputs[1].fill(password, timeout=120000)

            # 勾选协议 checkbox
            try:
                checkbox = await page.query_selector('input[type="checkbox"]')
                if checkbox:
                    await checkbox.check()
            except Exception:
                print("⚠️ 协议勾选框未找到或无法勾选，继续登录")

            # 点击登录按钮
            await page.click('button[type="submit"]', timeout=120000)

            # 等待登录成功
            try:
                await page.wait_for_url("**/server/**", timeout=60000)
            except PlaywrightTimeoutError:
                await page.wait_for_load_state("networkidle", timeout=30000)

            # ------------------ 打开服务器页面 ------------------
            await page.goto(server_url, timeout=90000)
            await page.wait_for_load_state("networkidle", timeout=30000)

            # ------------------ 点击续期按钮 ------------------
            add_button = page.locator('button:has-text("시간 추가")')
            if await add_button.count() == 0:
                add_button = page.locator('text=시간 추가')
            if await add_button.count() == 0:
                add_button = page.locator('button:has-text("Add Time")')

            if await add_button.count() == 0:
                screenshot_path = "no_button_found.png"
                await page.screenshot(path=screenshot_path, full_page=True)
                msg = "❌ 未找到 '시간 추가' 按钮，已保存截图"
                print(msg)
                await tg_notify_photo(screenshot_path, caption=msg)
                await tg_notify(msg)
                return

            await add_button.nth(0).click()
            await page.wait_for_timeout(30000)

            msg = f"✅ 续期操作已完成：{server_url}"
            print(msg)
            await tg_notify(msg)

        except Exception as e:
            msg = f"❌ 脚本异常: {repr(e)}"
            print(msg)
            screenshot_path = "error_screenshot.png"
            try:
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"📸 已保存错误截图：{screenshot_path}")
                await tg_notify_photo(screenshot_path, caption=msg)
            except Exception as se:
                print("⚠️ 无法保存或发送截图:", se)
            await tg_notify(msg)

        finally:
            await context.close()
            await browser.close()

if __name__ == "__main__":
    asyncio.run(add_server_time())
