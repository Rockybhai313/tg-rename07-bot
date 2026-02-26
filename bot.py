
import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# ================= ENV VARIABLES =================
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
PORT = int(os.getenv("PORT", 8000))
WORKERS = int(os.getenv("WORKERS", 3))
# =================================================

DOWNLOAD_DIR = "downloads"
THUMB_PATH = "thumbnail.jpg"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

app = Client("rename_pro_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

queue = asyncio.Queue()
user_state = {}

# -------- Health Server (Koyeb Fix) --------
async def health_server():
    async def handle(reader, writer):
        writer.close()
        await writer.wait_closed()
    server = await asyncio.start_server(handle, "0.0.0.0", PORT)
    print(f"Health server active on port {PORT}")
    async with server:
        await server.serve_forever()

# -------- Progress Bar --------
async def progress(current, total, message, action):
    if total == 0:
        return
    percent = current * 100 / total
    bar = "█" * int(percent//5) + "░" * (20-int(percent//5))
    try:
        await message.edit_text(f"{action}\n[{bar}] {percent:.1f}%")
    except:
        pass

# -------- Worker --------
async def worker(worker_id):
    while True:
        msg, new_name, caption = await queue.get()
        try:
            media = msg.document or msg.video or msg.audio
            original_name = media.file_name or "file.bin"
            final_name = new_name or original_name
            file_path = os.path.join(DOWNLOAD_DIR, final_name)

            status = await msg.reply_text(f"📥 Downloading (Worker {worker_id})...")
            downloaded = await msg.download(
                file_name=file_path,
                progress=progress,
                progress_args=(status,"📥 Downloading...")
            )

            await status.edit_text(f"📤 Uploading (Worker {worker_id})...")

            await msg.reply_document(
                document=downloaded,
                thumb=THUMB_PATH if os.path.exists(THUMB_PATH) else None,
                caption=caption or "",
                progress=progress,
                progress_args=(status,"📤 Uploading...")
            )

            await status.edit_text("✅ Completed")
            os.remove(downloaded)

        except Exception as e:
            await msg.reply_text(f"❌ Error: {e}")
        finally:
            queue.task_done()

# -------- Commands --------
@app.on_message(filters.command("start"))
async def start_handler(client, message):
    await message.reply_text(
        "🚀 Advanced Rename Bot Running\n"
        "Send 1GB–4GB file to start."
    )

@app.on_message(filters.command("admin") & filters.user(ADMIN_ID))
async def admin_handler(client, message):
    await message.reply_text(
        f"👑 Admin Panel\nQueue: {queue.qsize()}\nWorkers: {WORKERS}"
    )

@app.on_message(filters.command("setthumb") & filters.user(ADMIN_ID))
async def set_thumb(client, message):
    if message.reply_to_message and message.reply_to_message.photo:
        await message.reply_to_message.download(file_name=THUMB_PATH)
        await message.reply_text("✅ Thumbnail Saved")
    else:
        await message.reply_text("Reply to a photo with /setthumb")

# -------- Media Handler --------
@app.on_message(filters.document | filters.video | filters.audio)
async def media_handler(client, message):
    media = message.document or message.video or message.audio
    size = media.file_size

    if size < 1 * 1024**3 or size > 4 * 1024**3:
        await message.reply_text("❌ File must be 1GB–4GB")
        return

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✏ Rename", callback_data="rename"),
        InlineKeyboardButton("📝 Caption", callback_data="caption"),
        InlineKeyboardButton("➡ Skip", callback_data="skip")
    ]])

    user_state[message.from_user.id] = {"msg": message}
    await message.reply_text("Choose option:", reply_markup=keyboard)

# -------- Callback --------
@app.on_callback_query()
async def callback_handler(client, query):
    uid = query.from_user.id
    if uid not in user_state:
        return

    if query.data == "rename":
        user_state[uid]["step"] = "rename"
        await query.message.edit_text("Send new file name.")
    elif query.data == "caption":
        user_state[uid]["step"] = "caption"
        await query.message.edit_text("Send caption text.")
    elif query.data == "skip":
        await queue.put((user_state[uid]["msg"], None, ""))
        user_state.pop(uid)
        await query.message.edit_text("Added to queue ✅")

# -------- Text Input --------
@app.on_message(filters.text)
async def text_handler(client, message):
    uid = message.from_user.id
    if uid not in user_state:
        return

    step = user_state[uid].get("step")

    if step == "rename":
        user_state[uid]["new_name"] = message.text.strip()
        user_state[uid]["step"] = "caption_after_rename"
        await message.reply_text("Now send caption or type /skip")
    elif step == "caption":
        await queue.put((user_state[uid]["msg"], None, message.text))
        user_state.pop(uid)
        await message.reply_text("Added to queue ✅")
    elif step == "caption_after_rename":
        await queue.put((user_state[uid]["msg"], user_state[uid]["new_name"], message.text))
        user_state.pop(uid)
        await message.reply_text("Added to queue ✅")

# -------- Main --------
async def main():
    asyncio.create_task(health_server())
    for i in range(1, WORKERS+1):
        asyncio.create_task(worker(i))
    await app.start()
    print("Bot Running")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
