import os
import time
import asyncio
import sqlite3
from flask import Flask, request, jsonify
from pyrogram import Client
from pyrogram.errors import FloodWait

# --- Telegram Credentials ---
API_ID = 29969433
API_HASH = "884f9ffa4e8ece099cccccade82effac"
PHONE_NUMBER = "+919214045762"
TARGET_BOT = "@telebrecheddb_bot"
SESSION_FILE = os.path.join(os.path.dirname(__file__), "..", "user_session.session")

# --- Helper: check session ---
def check_and_fix_session():
    if os.path.exists(SESSION_FILE):
        try:
            conn = sqlite3.connect(SESSION_FILE)
            conn.execute("SELECT name FROM sqlite_master")
            conn.close()
        except sqlite3.DatabaseError:
            os.remove(SESSION_FILE)
check_and_fix_session()

# --- Translate Russian → English ---
def translate_text(text: str) -> str:
    replacements = {
        "Телефон": "Phone",
        "История изменения имени": "Name change history",
        "Интересовались этим": "Viewed by"
    }
    for ru, en in replacements.items():
        text = text.replace(ru, en)
    return text

# --- Send & Wait ---
async def send_and_wait(username: str):
    username = username.strip()
    if not username.lower().startswith("t.me/"):
        username_to_send = f"t.me/{username.lstrip('@')}"
    else:
        username_to_send = username

    async with Client(
        "user_session",
        api_id=API_ID,
        api_hash=API_HASH,
        phone_number=PHONE_NUMBER,
        no_updates=True,
        session_string=None  # uses SESSION_FILE automatically
    ) as tg_client:
        try:
            sent = await tg_client.send_message(TARGET_BOT, username_to_send)
        except FloodWait as e:
            await asyncio.sleep(e.value)
            sent = await tg_client.send_message(TARGET_BOT, username_to_send)
        except Exception as e:
            return f"⚠️ Error contacting bot: {e}"

        final_reply = None
        start_time = time.time()
        while time.time() - start_time < 25:
            async for msg in tg_client.get_chat_history(TARGET_BOT, limit=5):
                if msg.date > sent.date and msg.text:
                    final_reply = msg.text
                    break
            if final_reply:
                break
            await asyncio.sleep(1.5)

        if not final_reply:
            return "❌ No reply received from bot (timeout or bot slow)."

        return translate_text(final_reply)

# --- Flask App ---
app = Flask(__name__)

@app.route("/lookup")
def lookup():
    username = request.args.get("username")
    if not username:
        return jsonify({"error": "Missing 'username' parameter"}), 400

    try:
        result = asyncio.run(send_and_wait(username))
        return jsonify({
            "username": username,
            "result": result
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# --- Vercel Handler ---
def handler(request, *args, **kwargs):
    return app(request.environ, start_response=kwargs["start_response"])