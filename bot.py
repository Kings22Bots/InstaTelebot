import os
import glob
import subprocess
import logging
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- CONFIG ---
# Get your token from Railway Environment Variables
TOKEN = os.getenv('8636548271:AAEwAzj_qF3yS2opnixI_GbviPUpR6sobCo')
DOWNLOAD_DIR = 'downloads'
COOKIES = 'cookies.txt'

logging.basicConfig(level=logging.INFO)

async def download_media(url):
    """Downloads media using gallery-dl and yt-dlp."""
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    # gallery-dl: Best for carousels/images
    subprocess.run(['gallery-dl', '--cookies', COOKIES, '--directory', DOWNLOAD_DIR, url])
    
    # yt-dlp: Best for Reels/Videos (forces MP4 for Telegram)
    subprocess.run(['yt-dlp', '--cookies', COOKIES, '-f', 'b[ext=mp4]', '-P', DOWNLOAD_DIR, '-o', 'vid_%(id)s.%(ext)s', url])

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "instagram.com" not in url:
        return

    # User Feedback
    status = await update.message.reply_text("📥 Fetching media from Instagram...")

    # Cleanup: Delete files from the last request
    for f in glob.glob(f'{DOWNLOAD_DIR}/*'):
        try: os.remove(f)
        except: pass
    
    await download_media(url)
    
    media_group = []
    # Sort files to keep the original post order
    files = sorted(glob.glob(f'{DOWNLOAD_DIR}/*'))

    for path in files:
        ext = path.lower()
        if ext.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            media_group.append(InputMediaPhoto(open(path, 'rb')))
        elif ext.endswith(('.mp4', '.mov', '.m4v')):
            media_group.append(InputMediaVideo(open(path, 'rb')))

    if media_group:
        # Send in groups of 10 (Telegram's maximum album size)
        for i in range(0, len(media_group), 10):
            await update.message.reply_media_group(media_group[i:i+10])
    else:
        await update.message.reply_text("❌ Failed to fetch media. Check if the link is valid or if cookies.txt needs updating.")
    
    await status.delete()

def main():
    if not TOKEN:
        print("ERROR: BOT_TOKEN environment variable is missing!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("Bot is live and PUBLIC on Railway!")
    app.run_polling()

if __name__ == '__main__':
    main()
