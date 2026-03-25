import os
import glob
import subprocess
import logging
import random
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# Use Environment Variables for the Token on Railway!
TOKEN = os.getenv('BOT_TOKEN', '8636548271:AAEwAzj_qF3yS2opnixI_GbviPUpR6sobCo')
DOWNLOAD_DIR = '/tmp/downloads' # Use /tmp for Railway/Cloud hosting
COOKIES = 'cookies.txt'

logging.basicConfig(level=logging.INFO)

async def download_media(url):
    if not os.path.exists(DOWNLOAD_DIR):
        os.makedirs(DOWNLOAD_DIR)
    
    # Random delay to prevent "Automated Behavior" flag
    await asyncio.sleep(random.uniform(2, 5))

    # Video Downloader - The "Bulletproof" Merge Version
    y_cmd = [
        'yt-dlp',
        '--cookies', COOKIES,
        # This string finds the best mp4 video + m4a audio, or just the best single file
        '-f', 'bv[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best',
        '--merge-output-format', 'mp4',
        '--recode-video', 'mp4',
        '--postprocessor-args', 'ffmpeg:-c:v libx264 -c:a aac',
        '-P', DOWNLOAD_DIR,
        '-o', 'vid_%(id)s.%(ext)s',
        '--no-playlist',
        url
    ]

    # Gallery-dl for images
    g_cmd = ['gallery-dl', '--cookies', COOKIES, '--directory', DOWNLOAD_DIR, url]

    subprocess.run(g_cmd, capture_output=True)
    subprocess.run(y_cmd, capture_output=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "instagram.com" not in url: return

    status = await update.message.reply_text("⚡ Processing high-quality media...")

    # Clear temp folder
    for f in glob.glob(f'{DOWNLOAD_DIR}/*'):
        try: os.remove(f)
        except: pass
    
    await download_media(url)

    media_group = []
    files = sorted(glob.glob(f'{DOWNLOAD_DIR}/*'))

    for path in files:
        if path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            media_group.append(InputMediaPhoto(open(path, 'rb')))
        elif path.lower().endswith(('.mp4', '.mkv', '.mov')):
            media_group.append(InputMediaVideo(open(path, 'rb')))

    if media_group:
        await update.message.reply_media_group(media_group[:10])
    else:
        await update.message.reply_text("❌ Audio merge failed or link invalid. Check Railway logs.")

    await status.delete()

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == '__main__':
    main()
    
