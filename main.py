#!/usr/bin/env python3  
"""  
Telegram Auto Media Reposter (WEB SERVICE MODE)  
- Works on Render Web Service (hack)  
- Photo + Video  
- Multiple sources → targets  
- Queue-based (1-by-1)  
"""  
  
import os  
import re  
import asyncio  
import threading  
from flask import Flask  
  
from telethon import TelegramClient, events  
from telethon.sessions import StringSession  
  
# ================= CONFIG =================  
API_ID = int(os.getenv("API_ID"))  
API_HASH = os.getenv("API_HASH")  
STRING_SESSION = os.getenv("STRING_SESSION")  
  
SOURCE_GROUPS = [  
    -1002568532322,  
    -1003435489753,  
    -1002901100915,  
    -1003225039041,  
    -1003270523365  
]  
  
TARGET_CHANNELS = [  
    -1003034917757  
]  
  
LINK_BOT_USERNAME = "Kali_linux_phis_bot"  
  
FOOTER_TEXT = "\n\n━━━━━━━━━━━━━━\n🔥 🎬How To Watch \n\nhttps://t.me/join_545/51"  
# ========================================  
  
# -------- REGEX --------  
TERABOX_REGEX = re.compile(  
    r"https?://(?:www\.)?(?:"  
    r"terabox\.com|"  
    r"1024terabox\.com|"  
    r"teraboxapp\.com|"  
    r"terasharefile\.com|"  
    r"teraboxurl\.com|"  
    r"terabox\.link|"  
    r"teraboxapp\.link"  
    r")(?:/[^\s]+)?",  
    re.IGNORECASE  
)  
  
ALL_URL_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)  
  
# -------- TELETHON --------  
client = TelegramClient(  
    StringSession(STRING_SESSION),  
    API_ID,  
    API_HASH  
)  
  
post_queue = asyncio.Queue()  
helper_lock = asyncio.Lock()  
  
  
def clean_text(text: str) -> str:  
    text = TERABOX_REGEX.sub("", text)  
    text = ALL_URL_REGEX.sub("", text)  
    text = re.sub(r"\n\s*\n+", "\n\n", text)  
    return text.strip()  
  
  
# ================= TELEGRAM HANDLER (QUEUE ONLY) =================  
@client.on(events.NewMessage)  
async def on_new_message(event):  
    if event.chat_id not in SOURCE_GROUPS:  
        return  
    if not (event.video or event.photo):  
        return  
    if not event.text:  
        return  
    if not TERABOX_REGEX.search(event.text):  
        return  
  
    await post_queue.put(event)  
    print("📥 Queued post")  
  
  
# ================= PROCESS SINGLE POST =================  
async def process_event(event):  
    caption = event.text  
    terabox_link = TERABOX_REGEX.findall(caption)[0]  
  
    print(f"📦 Processing: {terabox_link}")  
  
    async with helper_lock:  
        async with client.conversation(LINK_BOT_USERNAME, timeout=30) as conv:  
            await conv.send_message(f"/link {terabox_link}")  
            reply = await conv.get_response()  
            new_link = reply.text.strip()  
            print(f"🔗 New link: {new_link}")  
  
    clean_caption = clean_text(caption)  
    final_caption = f"{clean_caption}\n\n{new_link}{FOOTER_TEXT}"  
  
    media = event.video or event.photo  
  
    for tgt in TARGET_CHANNELS:  
        try:  
            await client.send_file(  
                tgt,  
                media,  
                caption=final_caption,  
                supports_streaming=True  
            )  
            print(f"✅ Posted to {tgt}")  
        except Exception as e:  
            print(f"❌ Target {tgt} failed:", e)  
  
  
# ================= QUEUE WORKER =================  
async def queue_worker():  
    print("🧵 Queue worker started")  
    while True:  
        event = await post_queue.get()  
        try:  
            await process_event(event)  
  
            # 🔥 Add this line — 300 seconds = 5 minutes  
            print("⏳ Waiting 5 minutes before next post…")  
            await asyncio.sleep(300)  
  
        except Exception as e:  
            print("❌ Worker error:", e)  
  
        finally:  
            post_queue.task_done()  
  
  
# ================= BOT RUNNER =================  
def start_bot():  
    async def runner():  
        await client.start()  
        asyncio.create_task(queue_worker())  
        await client.run_until_disconnected()  
  
    asyncio.run(runner())  
  
  
# ================= FLASK WEB =================  
app = Flask(__name__)  
  
@app.route("/")  
def home():  
    return "Telegram bot is running"  
  
# Start bot in background thread  
threading.Thread(target=start_bot, daemon=True).start()  
  
# ================= ENTRY =================  
if __name__ == "__main__":  
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
