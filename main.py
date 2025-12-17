#!/usr/bin/env python3
"""
Telegram Auto Media Reposter (FINAL)
- StringSession
- Photo + Video
- Multiple sources → multiple targets
- Queue-based (one-by-one)
- TeraBox/TeraShare link replacement via helper bot
- Removes ALL other links
- Adds footer
"""

import re
import asyncio
from telethon import TelegramClient, events
from telethon.sessions import StringSession

# ==== CONFIGURATION ====
API_ID = 25240346     # your api_id
API_HASH = "b8849fd945ed9225a002fda96591b6ee"
STRING_SESSION = "1BJWap1wBu7q09NquMn4nwKye3kuNInfdwziadV9LX6XMJX8QOQYd1xamhHYnCxIK5rqqPhgUC8i4HXxsZAfsopI3FPQ2s1C7STe9QIUx1MY-QTyVLDc9R1RGxX_7BifPx0lVfjY84qNjr_5rln48FmthESgDmpWQhspvv4KNGA9Y3VrVxf7lyr-qx8mXwVl1QE-tgue-SncSIjlg6RMhL8hjh3iQixeqy1YipLVs3CJ6nED7TkfsEHENCah3AJLWDRlkKz5W7pOXnqQ4vYPytHZrsBbLmfxKS-XJB5tDdz30yaQV_ASqlcxaAEvXCFjqtebOkx5LG64RCYlahHykrOXQiiBgXEQ="


SOURCE_GROUPS = [
    -1002568532322,
    -1003435489753,
    -1002901100915
]

TARGET_CHANNELS = [
    -1003296614035
]

LINK_BOT_USERNAME = "Kali_linux_phis_bot"

FOOTER_TEXT = "\n\n━━━━━━━━━━━━━━\n🔥 🎬How To Watch \n\nhttps://t.me/join_545/51"
# ============================

client = TelegramClient(
    StringSession(STRING_SESSION),
    API_ID,
    API_HASH
)

# -------- REGEX --------
TERABOX_REGEX = re.compile(
    r"https?://(?:www\.)?(?:"
    r"terabox\.com|"
    r"1024terabox\.com|"
    r"teraboxapp\.com|"
    r"terasharefile\.com|"
    r"terabox\.link|"
    r"teraboxapp\.link"
    r")(?:/[^\s]+)?",
    re.IGNORECASE
)

ALL_URL_REGEX = re.compile(r"https?://\S+", re.IGNORECASE)

# -------- QUEUE & LOCK --------
post_queue = asyncio.Queue()
helper_lock = asyncio.Lock()


def clean_text(text: str) -> str:
    """Remove all links and normalize text"""
    text = TERABOX_REGEX.sub("", text)
    text = ALL_URL_REGEX.sub("", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


# ================= EVENT HANDLER (QUEUE ONLY) =================
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
    print("📥 Queued new post")


# ================= WORKER (ONE BY ONE) =================
async def queue_worker():
    print("🧵 Queue worker started")
    while True:
        event = await post_queue.get()
        try:
            await process_event(event)
        except Exception as e:
            print("❌ Worker error:", e)
        finally:
            post_queue.task_done()


# ================= PROCESS SINGLE POST =================
async def process_event(event):
    caption = event.text
    terabox_link = TERABOX_REGEX.findall(caption)[0]

    print(f"📦 Processing: {terabox_link}")

    # 🔒 One helper-bot conversation at a time
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
                file=media,
                caption=final_caption,
                supports_streaming=True
            )
            print(f"✅ Posted to {tgt}")
        except Exception as e:
            print(f"❌ Target {tgt} failed:", e)


# ================= MAIN =================
async def main():
    print("🚀 Auto Media Reposter started")
    await client.start()

    # Start ONE worker → serial processing
    asyncio.create_task(queue_worker())

    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())