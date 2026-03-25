import os
import glob
import subprocess
import logging
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
TOKEN = '8636548271:AAEwAzj_qF3yS2opnixI_GbviPUpR6sobCo'  
DOWNLOAD_DIR = 'temp_downloads'
COOKIES = 'cookies.txt'
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'

# Setup logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def download_media(url):
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    # 1. gallery-dl for images
    g_cmd = [
        'gallery-dl',
        '--cookies', COOKIES,
        '--user-agent', USER_AGENT,
        '--directory', DOWNLOAD_DIR,
        '--filename', 'img_{id}_{num}.{extension}',
        url
    ]
    
    # 2. yt-dlp: Raw highest quality, merged into MKV to prevent codec crashes
    y_cmd = [
        'yt-dlp',
        '--cookies', COOKIES,
        '--user-agent', USER_AGENT,
        '-f', 'bv*+ba/b',               # Grabs maximum video and audio
        '--merge-output-format', 'mkv', # The universal container to prevent merge failures
        '-P', DOWNLOAD_DIR,
        '-o', 'vid_%(id)s.%(ext)s',
        '--no-playlist',
        url
    ]

    subprocess.run(g_cmd, capture_output=True)
    subprocess.run(y_cmd, capture_output=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "instagram.com" not in url:
        return

    status = await update.message.reply_text("🔍 Extracting raw highest-quality media...")

    for f in glob.glob(f'{DOWNLOAD_DIR}/*'):
        try: os.remove(f)
        except: pass
    
    await download_media(url)

    media_group = []
    downloaded_files = sorted(glob.glob(f'{DOWNLOAD_DIR}/*'))

    for path in downloaded_files:
        ext = path.lower()
        try:
            if ext.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                media_group.append(InputMediaPhoto(open(path, 'rb')))
            # Ensured mkv and webm are accepted by Telegram here:
            elif ext.endswith(('.mp4', '.mov', '.m4v', '.mkv', '.webm')): 
                media_group.append(InputMediaVideo(open(path, 'rb')))
        except Exception as e:
            logging.error(f"Error opening file {path}: {e}")

    if media_group:
        for i in range(0, len(media_group), 10):
            await update.message.reply_media_group(media_group[i:i+10])
    else:
        await update.message.reply_text("❌ Failed to grab media. Ensure cookies.txt is valid.")

    await status.delete()

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Bot is running with raw quality extraction...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
