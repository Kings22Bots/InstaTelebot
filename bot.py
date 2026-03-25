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
TOKEN = os.getenv('BOT_TOKEN', '8636548271:AAEwAzj_qF3yS2opnixI_GbviPUpR6sobCo')
DOWNLOAD_DIR = '/tmp/downloads'
COOKIES = 'cookies.txt'

logging.basicConfig(level=logging.INFO)

# --- ANTI-DETECTION HEADERS ---
UA_STRING = 'Mozilla/5.0 (Linux; Android 14; iQOO Z9x) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36'

STEALTH_ARGS = [
    '--header', f'User-Agent: {UA_STRING}',
    '--header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    '--header', 'Accept-Language: en-US,en;q=0.9',
    '--header', 'Sec-Ch-Ua-Platform: "Android"',
]

def get_formats(url):
    """Aggressively extracts qualities, handling hidden resolutions and 4K/HDR."""
    cmd = [
        'yt-dlp', '--cookies', COOKIES, *STEALTH_ARGS,
        '--dump-json', '--no-playlist', url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0: 
        logging.error(f"yt-dlp JSON Error: {result.stderr}")
        return None
    
    try:
        data = json.loads(result.stdout)
        formats = []
        
        for f in data.get('formats', []):
            ext = f.get('ext', '').lower()
            vcodec = f.get('vcodec', 'none')
            
            # Skip pure audio or image streams
            if (vcodec == 'none' and f.get('acodec') != 'none') or ext in ['jpg', 'webp', 'png', 'm4a']:
                continue
            
            height = f.get('height')
            width = f.get('width')
            fps = f.get('fps')
            dynamic_range = f.get('dynamic_range', '')
            format_id = f.get('format_id')
            
            display_res = height if height else width
            
            # If resolution exists, build a detailed label
            if display_res:
                fps_str = f" {int(fps)}fps" if fps and fps >= 50 else ""
                hdr_str = f" HDR" if dynamic_range and 'HDR' in dynamic_range else ""
                label = f"{display_res}p{fps_str}{hdr_str} ({ext})"
                formats.append({'label': label, 'id': format_id, 'h': display_res})
                
            # Fallback: if resolution is hidden but it's a valid video file
            elif ext in ['mp4', 'webm', 'mkv']:
                label = f"Standard Quality ({ext})"
                formats.append({'label': label, 'id': format_id, 'h': 0})
        
        if not formats: 
            return None
            
        # Remove duplicates, keep highest quality at the top
        unique = {f['label']: f for f in formats}.values()
        return sorted(unique, key=lambda x: x['h'] if x['h'] else 0, reverse=True)
        
    except Exception as e:
        logging.error(f"Format extraction error: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "instagram.com" not in url: return

    wait_msg = await update.message.reply_text("🔎 Scanning for qualities (4K/HDR)...")
    
    # Random delay to simulate human timing
    await asyncio.sleep(random.uniform(2.0, 4.5))
    
    formats = await asyncio.to_thread(get_formats, url)
    
    if not formats:
        await wait_msg.edit_text("📸 No specific video qualities found. Attempting direct grab...")
        await start_download(update.message, url, "best", wait_msg, context, "mp4")
        return

    keyboard = []
    for f in formats:
        btn_id = f['id']
        ext = f['label'].split('(')[-1].replace(')', '')
        # Store data in context to bypass Telegram's 64-byte callback limit
        context.user_data[btn_id] = {'url': url, 'ext': ext}
        keyboard.append([InlineKeyboardButton(f"Download {f['label']}", callback_data=f"dl|{btn_id}")])

    await wait_msg.edit_text("✅ Select Quality:", reply_markup=InlineKeyboardMarkup(keyboard))

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    format_id = query.data.split('|')[1]
    data = context.user_data.get(format_id)

    if not data:
        await query.edit_message_text("❌ Link expired. Please resend the URL.")
        return

    await start_download(query.message, data['url'], format_id, query.message, context, data['ext'])

async def start_download(message, url, format_id, status_msg, context, target_ext):
    if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)
    for f in glob.glob(f'{DOWNLOAD_DIR}/*'): 
        try: os.remove(f)
        except: pass

    await status_msg.edit_text(f"⏳ Downloading... preserving original quality.")

    # Prevent WebM merging errors by wrapping in MKV container
    merge_format = 'mkv' if target_ext == 'webm' else 'mp4'

    y_cmd = [
        'yt-dlp', '--cookies', COOKIES, *STEALTH_ARGS,
        '-f', f"{format_id}+bestaudio/best",
        '--merge-output-format', merge_format,
        '--postprocessor-args', 'ffmpeg:-c:a aac', # Ensures audio plays everywhere
        '-P', DOWNLOAD_DIR, '-o', 'vid_%(id)s.%(ext)s', url
    ]
    
    g_cmd = [
        'gallery-dl', '--cookies', COOKIES, 
        '--user-agent', UA_STRING, 
        '--directory', DOWNLOAD_DIR, url
    ]

    await asyncio.to_thread(subprocess.run, g_cmd, capture_output=True)
    await asyncio.to_thread(subprocess.run, y_cmd, capture_output=True)

    files = sorted(glob.glob(f'{DOWNLOAD_DIR}/*'))
    media = []
    
    for path in files:
        ext = path.lower()
        if ext.endswith(('.jpg', '.jpeg', '.png', '.webp')):
            media.append(InputMediaPhoto(open(path, 'rb')))
        elif ext.endswith(('.mp4', '.mkv', '.webm', '.mov')):
            media.append(InputMediaVideo(open(path, 'rb')))

    if media:
        try:
            for i in range(0, len(media), 10):
                await message.reply_media_group(media[i:i+10])
            await status_msg.delete()
        except Exception as e:
            await status_msg.edit_text(f"❌ Upload failed. File might exceed Telegram's 50MB bot limit.")
    else:
        await status_msg.edit_text("❌ Download failed. Try replacing your cookies.txt.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 Bot is running with the aggressive scanner and 4K support...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
