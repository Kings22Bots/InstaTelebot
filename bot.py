import os
import glob
import subprocess
import logging
import json
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- CONFIGURATION ---
# Use an environment variable on Railway for security, or keep this as fallback
TOKEN = os.getenv('BOT_TOKEN', '8636548271:AAEwAzj_qF3yS2opnixI_GbviPUpR6sobCo')
DOWNLOAD_DIR = '/tmp/downloads'
COOKIES = 'cookies.txt'

# Stealth headers to mimic a real Android device (iQOO Z9x style)
STEALTH_ARGS = [
    '--header', 'User-Agent: Mozilla/5.0 (Linux; Android 14; iQOO Z9x) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
    '--header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    '--header', 'Accept-Language: en-US,en;q=0.9',
    '--header', 'Sec-Ch-Ua-Platform: "Android"',
    '--header', 'Sec-Fetch-Mode: navigate'
]

logging.basicConfig(level=logging.INFO)

def get_formats(url):
    """Fetches available resolutions without downloading."""
    cmd = [
        'yt-dlp', '--cookies', COOKIES,
        *STEALTH_ARGS,
        '--dump-json', '--no-playlist', url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        return None
    
    try:
        data = json.loads(result.stdout)
        formats = []
        for f in data.get('formats', []):
            if f.get('vcodec') != 'none' and f.get('height'):
                label = f"{f['height']}p ({f['ext']})"
                formats.append({'label': label, 'id': f['format_id']})
        
        # Unique resolutions only, sorted highest to lowest
        unique = {f['label']: f for f in formats}.values()
        return sorted(unique, key=lambda x: int(x['label'].split('p')[0]), reverse=True)
    except:
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "instagram.com" not in url: return

    wait_msg = await update.message.reply_text("🔎 Analyzing video qualities...")
    
    formats = await asyncio.to_thread(get_formats, url)
    
    if not formats:
        # If no video formats, try direct download (could be a photo)
        await wait_msg.edit_text("📸 No specific video qualities found. Attempting direct grab...")
        await start_download(update, url, "best", wait_msg)
        return

    keyboard = []
    for f in formats:
        # Store URL in user_data because it's too long for callback_data
        context.user_data[f['id']] = url
        keyboard.append([InlineKeyboardButton(f"Download {f['label']}", callback_data=f"dl|{f['id']}")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await wait_msg.edit_text("✅ Select Quality:", reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    format_id = query.data.split('|')[1]
    url = context.user_data.get(format_id)

    if not url:
        await query.edit_message_text("❌ Link expired. Please resend the URL.")
        return

    await start_download(query.message, url, format_id, query.message)

async def start_download(message, url, format_id, status_msg):
    if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)
    for f in glob.glob(f'{DOWNLOAD_DIR}/*'): os.remove(f)

    await status_msg.edit_text(f"⏳ Processing {format_id}... This takes a moment.")

    # Combined yt-dlp command with merging and recoding for Audio
    y_cmd = [
        'yt-dlp', '--cookies', COOKIES,
        *STEALTH_ARGS,
        '-f', f"{format_id}+bestaudio/best",
        '--merge-output-format', 'mp4',
        '--recode-video', 'mp4',
        '--postprocessor-args', 'ffmpeg:-c:v libx264 -c:a aac',
        '-P', DOWNLOAD_DIR,
        '-o', 'vid_%(id)s.%(ext)s',
        url
    ]
    
    # gallery-dl as secondary for images
    g_cmd = ['gallery-dl', '--cookies', COOKIES, '--directory', DOWNLOAD_DIR, url]

    await asyncio.to_thread(subprocess.run, g_cmd, capture_output=True)
    await asyncio.to_thread(subprocess.run, y_cmd, capture_output=True)

    files = sorted(glob.glob(f'{DOWNLOAD_DIR}/*'))
    media_group = []

    for path in files:
        if path.lower().endswith(('.jpg', '.jpeg', '.png', '.webp')):
            media_group.append(InputMediaPhoto(open(path, 'rb')))
        elif path.lower().endswith(('.mp4', '.mkv', '.mov')):
            media_group.append(InputMediaVideo(open(path, 'rb')))

    if media_group:
        await message.reply_media_group(media_group[:10])
        await status_msg.delete()
    else:
        await status_msg.edit_text("❌ Download failed. Instagram may have blocked the session.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 Bot is LIVE on Railway...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
