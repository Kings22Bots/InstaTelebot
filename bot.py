import os
import glob
import subprocess
import logging
import json
import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, InputMediaVideo
from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# Use Environment Variables for the Token on Railway
TOKEN = os.getenv('BOT_TOKEN', '8636548271:AAEwAzj_qF3yS2opnixI_GbviPUpR6sobCo')
DOWNLOAD_DIR = '/tmp/downloads'
COOKIES = 'cookies.txt'

logging.basicConfig(level=logging.INFO)

# Anti-Detection: Mimic your iQOO Z9x device
UA_STRING = 'Mozilla/5.0 (Linux; Android 14; iQOO Z9x) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36'

STEALTH_ARGS = [
    '--header', f'User-Agent: {UA_STRING}',
    '--header', 'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    '--header', 'Accept-Language: en-US,en;q=0.9',
    '--header', 'Sec-Ch-Ua-Platform: "Android"',
]

def get_formats(url):
    """Extracts all qualities including 4K, HDR, WebM, and MKV."""
    cmd = [
        'yt-dlp', '--cookies', COOKIES, *STEALTH_ARGS,
        '--dump-json', '--no-playlist', url
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0: return None
    
    try:
        data = json.loads(result.stdout)
        formats = []
        for f in data.get('formats', []):
            if f.get('vcodec') != 'none' and f.get('height'):
                height = f.get('height')
                fps = f.get('fps')
                ext = f.get('ext', 'mp4')
                dynamic_range = f.get('dynamic_range', '')
                
                # Format the label (e.g., "1080p60 HDR10+ (webm)")
                fps_str = f"{int(fps)}" if fps and fps >= 50 else ""
                hdr_str = f" {dynamic_range}" if dynamic_range and 'HDR' in dynamic_range else ""
                label = f"{height}p{fps_str}{hdr_str} ({ext})"
                
                formats.append({
                    'label': label, 
                    'id': f['format_id'], 
                    'h': height
                })
        
        # Remove duplicates, keeping the highest quality ones
        unique = {f['label']: f for f in formats}.values()
        return sorted(unique, key=lambda x: x['h'], reverse=True)
    except Exception as e:
        logging.error(f"Format extraction error: {e}")
        return None

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "instagram.com" not in url: return

    wait_msg = await update.message.reply_text("🔎 Scanning for 4K/HDR qualities safely...")
    
    # 1. Add random delay to prevent automated behavior block
    await asyncio.sleep(random.uniform(2.0, 4.5))
    
    formats = await asyncio.to_thread(get_formats, url)
    
    if not formats:
        await wait_msg.edit_text("📸 No video formats found. Attempting direct grab...")
        await start_download(update.message, url, "best", wait_msg, context)
        return

    keyboard = []
    for f in formats:
        # Save URL and format extension to context to bypass Telegram button size limits
        btn_id = f['id']
        context.user_data[btn_id] = {'url': url, 'ext': f['label'].split('(')[-1].replace(')', '')}
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

async def start_download(message, url, format_id, status_msg, context, target_ext="mp4"):
    if not os.path.exists(DOWNLOAD_DIR): os.makedirs(DOWNLOAD_DIR)
    for f in glob.glob(f'{DOWNLOAD_DIR}/*'): 
        try: os.remove(f)
        except: pass

    await status_msg.edit_text(f"⏳ Downloading {format_id}... preserving original quality.")

    # We use MKV as the universal merge format if WebM is selected, 
    # to avoid codec clashes when combining weird video and audio formats.
    merge_format = 'mkv' if target_ext == 'webm' else 'mp4'

    y_cmd = [
        'yt-dlp', '--cookies', COOKIES, *STEALTH_ARGS,
        '-f', f"{format_id}+bestaudio/best",
        '--merge-output-format', merge_format,
        # Postprocessor ensures audio works without downscaling your 4K video
        '--postprocessor-args', 'ffmpeg:-c:a aac', 
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
            await status_msg.edit_text(f"❌ Telegram upload failed. It might be too large (>50MB).")
    else:
        await status_msg.edit_text("❌ Download failed. Session may be blocked by Instagram.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(button_callback))
    print("🚀 Bot is running with 4K/WebM selection and Anti-Detection...")
    app.run_polling()

if __name__ == '__main__':
    main()
    
