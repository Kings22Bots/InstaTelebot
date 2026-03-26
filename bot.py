import os
import glob
import subprocess
import logging
import random
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo, InputMediaDocument
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
TOKEN = os.getenv('BOT_TOKEN', '8636548271:AAEwAzj_qF3yS2opnixI_GbviPUpR6sobCo')
DOWNLOAD_DIR = '/tmp/downloads'
COOKIES = 'cookies.txt'

logging.basicConfig(level=logging.INFO)

# --- ADVANCED STEALTH HEADERS ---
# Using a specific, modern mobile fingerprint to authenticate the session naturally
UA_STRING = 'Mozilla/5.0 (Linux; Android 14; iQOO Z9x) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36'

STEALTH_ARGS = [
    '--header', f'User-Agent: {UA_STRING}',
    '--header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    '--header', 'Accept-Language: en-US,en;q=0.9',
    '--header', 'Sec-Ch-Ua-Platform: "Android"',
    '--header', 'Sec-Fetch-Dest: document',
    '--header', 'Sec-Fetch-Mode: navigate',
    '--header', 'Sec-Fetch-Site: none',
    '--header', 'Upgrade-Insecure-Requests: 1'
]

async def download_media(url):
    if not os.path.exists(DOWNLOAD_DIR): 
        os.makedirs(DOWNLOAD_DIR)
    
    # Anti-Detection: Heavier random delay to mimic human feed-scrolling
    await asyncio.sleep(random.uniform(4.0, 8.5))

    # yt-dlp: Grabs highest raw video + audio. No forced merging format.
    y_cmd = [
        'yt-dlp', '--cookies', COOKIES, *STEALTH_ARGS,
        '-f', 'bv*+ba/b', 
        '-P', DOWNLOAD_DIR, 
        '-o', 'vid_%(id)s.%(ext)s', 
        '--no-playlist', url
    ]
    
    # gallery-dl: Focuses on original image quality
    g_cmd = [
        'gallery-dl', '--cookies', COOKIES, 
        '--user-agent', UA_STRING, 
        '--directory', DOWNLOAD_DIR, url
    ]

    await asyncio.to_thread(subprocess.run, g_cmd, capture_output=True)
    await asyncio.to_thread(subprocess.run, y_cmd, capture_output=True)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "instagram.com" not in url: return

    status = await update.message.reply_text("🛡️ Bypassing detection & extracting raw media...")
    
    for f in glob.glob(f'{DOWNLOAD_DIR}/*'): 
        try: os.remove(f)
        except: pass
    
    await download_media(url)

    files = sorted(glob.glob(f'{DOWNLOAD_DIR}/*'))
    
    playable_media = []
    document_media = []
    
    # Smart Sorting: Separates playable formats from document formats
    for path in files:
        ext = path.lower()
        if ext.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            playable_media.append(InputMediaPhoto(open(path, 'rb')))
        elif ext.endswith(('.mp4', '.mov')):
            playable_media.append(InputMediaVideo(open(path, 'rb')))
        elif ext.endswith(('.webm', '.mkv')):
            document_media.append(path) # Kept as string paths for document sending

    # 1. Send Playable Media (Photos & MP4s grouped together)
    if playable_media:
        try:
            for i in range(0, len(playable_media), 10):
                await update.message.reply_media_group(playable_media[i:i+10])
        except Exception as e:
            logging.error(f"Telegram Playable Upload Error: {e}")

    # 2. Send Raw Documents (WebM, MKV) separately
    if document_media:
        for doc_path in document_media:
            try:
                await update.message.reply_document(
                    document=open(doc_path, 'rb'), 
                    caption="📄 Raw High-Quality Format"
                )
            except Exception as e:
                logging.error(f"Telegram Document Upload Error: {e}")

    if not playable_media and not document_media:
        await status.edit_text("❌ Download failed. The security wall blocked the request or cookies expired.")
    else:
        await status.delete()

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Stealth Bot is LIVE with Smart Format Sorting...")
    app.run_polling()

if __name__ == '__main__':
    main()
