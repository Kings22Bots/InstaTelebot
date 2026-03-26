import os
import glob
import subprocess
import logging
import random
import asyncio
from telegram import Update, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, filters, ContextTypes

# --- CONFIGURATION ---
TOKEN = '8636548271:AAEwAzj_qF3yS2opnixI_GbviPUpR6sobCo'
DOWNLOAD_DIR = '/tmp/downloads'
COOKIES = 'cookies.txt'

logging.basicConfig(level=logging.INFO)

# --- ADVANCED STEALTH HEADERS ---
# Perfectly synced to your Kiwi Browser session
UA_STRING = 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36'

# Upgraded syntax with Origin and Referer to bypass GraphQL CORS checks
STEALTH_ARGS = [
    '--user-agent', UA_STRING,
    '--add-header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    '--add-header', 'Accept-Language: en-US,en;q=0.9',
    '--add-header', 'Sec-Ch-Ua-Platform: "Android"',
    '--add-header', 'Sec-Fetch-Dest: document',
    '--add-header', 'Sec-Fetch-Mode: navigate',
    '--add-header', 'Sec-Fetch-Site: same-origin',
    '--add-header', 'Origin: https://www.instagram.com',
    '--add-header', 'Referer: https://www.instagram.com/',
]

async def download_media(url):
    if not os.path.exists(DOWNLOAD_DIR): 
        os.makedirs(DOWNLOAD_DIR)
    
    # Human-like delay
    await asyncio.sleep(random.uniform(3.5, 7.0))

    # 1. Fetch the Playable Video (Forces the best MP4 stream)
    y_cmd_playable = [
        'yt-dlp', '--cookies', COOKIES, *STEALTH_ARGS,
        '-f', 'bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best', 
        '--merge-output-format', 'mp4',
        '-P', DOWNLOAD_DIR, 
        '-o', 'playable_%(id)s.%(ext)s', 
        '--no-playlist', url
    ]

    # 2. Fetch the Raw Document (Grabs the absolute max quality, e.g., WebM/MKV)
    y_cmd_raw = [
        'yt-dlp', '--cookies', COOKIES, *STEALTH_ARGS,
        '-f', 'bv*+ba/b', 
        '-P', DOWNLOAD_DIR, 
        '-o', 'raw_%(id)s.%(ext)s', 
        '--no-playlist', url
    ]
    
    # 3. Fetch Images (if it's a carousel)
    g_cmd = [
        'gallery-dl', '--cookies', COOKIES, 
        '--user-agent', UA_STRING, 
        '--add-header', 'Referer: https://www.instagram.com/',
        '--directory', DOWNLOAD_DIR, url
    ]

    # Run downloads concurrently and capture output for debugging
    g_res, y_play_res, y_raw_res = await asyncio.gather(
        asyncio.to_thread(subprocess.run, g_cmd, capture_output=True, text=True),
        asyncio.to_thread(subprocess.run, y_cmd_playable, capture_output=True, text=True),
        asyncio.to_thread(subprocess.run, y_cmd_raw, capture_output=True, text=True)
    )

    # Print exact background errors to the Railway console if they fail
    if y_play_res.returncode != 0:
        logging.error(f"yt-dlp Playable Error: {y_play_res.stderr}")
    if y_raw_res.returncode != 0:
        logging.error(f"yt-dlp Raw Error: {y_raw_res.stderr}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "instagram.com" not in url: return

    status = await update.message.reply_text("🛡️ Bypassing security & fetching Playable + Raw Formats...")
    
    # Clean up old files
    for f in glob.glob(f'{DOWNLOAD_DIR}/*'): 
        try: os.remove(f)
        except: pass
    
    await download_media(url)

    files = sorted(glob.glob(f'{DOWNLOAD_DIR}/*'))
    
    playable_media = []
    document_media = []
    
    # Strict Sorting Logic
    for path in files:
        ext = path.lower()
        filename = os.path.basename(path)

        if ext.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            playable_media.append(InputMediaPhoto(open(path, 'rb')))
        elif filename.startswith('playable_') and ext.endswith('.mp4'):
            playable_media.append(InputMediaVideo(open(path, 'rb')))
        elif filename.startswith('raw_'):
            document_media.append(path)

    # 1. Send Playable Media (Photos & Inline Videos)
    if playable_media:
        try:
            for i in range(0, len(playable_media), 10):
                await update.message.reply_media_group(playable_media[i:i+10])
        except Exception as e:
            logging.error(f"Playable Upload Error: {e}")

    # 2. Send Raw Document (The untouch 1080p/4K Original)
    if document_media:
        for doc_path in document_media:
            try:
                await update.message.reply_document(
                    document=open(doc_path, 'rb'), 
                    caption="📄 Original Uncompressed Source Format"
                )
            except Exception as e:
                logging.error(f"Document Upload Error: {e}")

    if not playable_media and not document_media:
        await status.edit_text("❌ Download failed. Check Railway 'Deploy Logs' for the exact error.")
    else:
        await status.delete()

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Dual-Fetch Mode is LIVE with Full HTTP Routing...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
