import base64
import json
import re
import urllib.error
import urllib.parse
import urllib.request
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command

# ضع توكن بوت تليجرام الخاص بك هنا مباشرة، أو اجعله يقرأه تلقائياً من متغيرات الاستضافة (Environment Variables)
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE")

bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

def hide_lists(sessionid: str) -> dict:
    if not sessionid or any(ord(c) <= 32 or ord(c) >= 127 or c in ';,"\\' for c in sessionid):
        raise ValueError("Enter only the sessionid cookie value, without 'sessionid='.")
    match = re.fullmatch(r"([1-9][0-9]*)(?::|%3[aA]).+", sessionid)
    if not match:
        raise ValueError("Invalid sessionid format: expected a numeric user ID followed by ':' or '%3A'.")
    user_id = match.group(1)
    token = base64.b64encode(json.dumps({
        "ds_user_id": user_id,
        "sessionid": sessionid,
        "should_use_header_over_cookies": True,
    }, separators=(",", ":")).encode()).decode("ascii")
    authorization = "Bearer IGT:2:" + token
    name = "IGSettingsBooleanMutation"
    form = {
        "method": "post",
        "format": "json",
        "server_timestamps": "true",
        "locale": "user",
        "fb_api_req_friendly_name": name,
        "client_doc_id": "2669261950526978627082629536",
        "variables": json.dumps({
            "setting_id": "hide_followers_following_list",
            "allow_error_codes": True,
            "callsite": "account_privacy",
            "value": True,
        }),
    }
    request = urllib.request.Request(
        "https://i.instagram.com/graphql/query",
        data=urllib.parse.urlencode(form).encode(),
        headers={
            "Authorization": authorization,
            "Cookie": f"sessionid={sessionid}; ds_user_id={user_id}",
            "IG-INTENDED-USER-ID": user_id,
            "X-IG-App-ID": "124024574287414",
            "X-Auth-Type": "instagram",
            "User-Agent": "Instagram 453.0.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept-Encoding": "identity",
            "X-GraphQL-Client-Library": "pando",
            "X-FB-Friendly-Name": name,
        },
        method="POST",
    )

    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            raise RuntimeError("Redirect refused; credentials were not forwarded.")

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=15) as response:
            raw = response.read(1024 * 1024 + 1)
            if len(raw) > 1024 * 1024:
                raise RuntimeError("Response too large.")
            return json.loads(raw)
    except urllib.error.HTTPError as error:
        code = error.code
        with error:
            raw = error.read(16385)
        details = {}
        try:
            body = json.loads(raw) if len(raw) <= 16384 else {}
            if isinstance(body, dict):
                for key in ("message", "error_type", "status", "code"):
                    if isinstance(body.get(key), (str, int, bool)):
                        details[key] = body[key]
        except (ValueError, UnicodeError):
            pass
        text = json.dumps(details) if details else "No selected JSON error details."
        secrets = {authorization, token, sessionid, urllib.parse.unquote(sessionid),
                   urllib.parse.quote(sessionid, safe="")}
        for secret in sorted(secrets, key=len, reverse=True):
            if secret:
                text = text.replace(secret, "<REDACTED>")
        raise RuntimeError(f"HTTP {code}: {text[:1500]}. No retry performed.") from None


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 أهلاً بك في بوت إخفاء قوائم انستجرام.\n\n"
        "أرسل لي الـ `sessionid` الخاص بحسابك وسأقوم بتفعيل خيار إخفاء المتابعين/المتابعون فوراً."
    )


@dp.message()
async def handle_session(message: types.Message):
    sessionid = message.text.strip()
    
    # تجاهل الأوامر الأخرى إن وجدت
    if sessionid.startswith("/"):
        return

    wait_msg = await message.answer("⏳ جاري معالجة الطلب وإرساله إلى إنستجرام...")
    
    try:
        body = hide_lists(sessionid)
        data = body.get("data") if isinstance(body, dict) else None
        root = "xdt_api__v1__settings__set_bool"
        matches = [value for key, value in data.items()
                   if key == root or key.startswith(root + "(")] if isinstance(data, dict) else []
        result = matches[0] if len(matches) == 1 and isinstance(matches[0], dict) else {}
        
        if (not isinstance(body, dict) or body.get("errors") or body.get("error")
                or body.get("status") == "fail" or result.get("value") is not True
                or any(result.get(key) for key in (
                    "error_name_value", "errorNameValue", "fallback_message", "fallbackMessage"
                ))):
            await bot.edit_message_text(
                "❌ فشل التنفيذ: لم يعتمد إنستجرام التغيير. تأكد من صحة وصلاحية الـ sessionid.",
                chat_id=message.chat.id,
                message_id=wait_msg.message_id
            )
            return

        await bot.edit_message_text(
            "✅ **تم بنجاح!** استاب الإعداد وإخفاء قوائم المتابعين لحسابك.",
            chat_id=message.chat.id,
            message_id=wait_msg.message_id
        )
        
    except ValueError as err:
        await bot.edit_message_text(f"⚠️ خطأ في الصيغة: {err}", chat_id=message.chat.id, message_id=wait_msg.message_id)
    except RuntimeError as err:
        await bot.edit_message_text(f"❌ خطأ من الخادم: {err}", chat_id=message.chat.id, message_id=wait_msg.message_id)
    except Exception:
        await bot.edit_message_text("❌ حدث خطأ غير متوقع أو أن الشبكة لا تستجيب.", chat_id=message.chat.id, message_id=wait_msg.message_id)


async def main():
    print("Bot is starting...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped.")
