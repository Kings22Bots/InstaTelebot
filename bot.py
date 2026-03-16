import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from telebot import apihelper
import yt_dlp
import os
import time
import glob

apihelper.CONNECT_TIMEOUT = 9999
apihelper.READ_TIMEOUT = 9999

TOKEN = "8636548271:AAEaR2ihZn57PIZKfWxATk57Zha_SBENunU"
bot = telebot.TeleBot(TOKEN)

url_cache = {}

def safe_edit(text, chat_id, message_id, markup=None, parse_mode=None):
try:
bot.edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=markup, parse_mode=parse_mode)
except Exception:
pass

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
bot.reply_to(message, "👋 Send a link! I will generate a format table including HDR.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
url = message.text.strip()

if not url.startswith(('http://', 'https://')):
    bot.reply_to(message, "Please send a valid URL starting with http:// or https://")
    return

status_msg = bot.reply_to(message, "🔍 Scanning formats...")

ydl_opts = {
    'quiet': True,
    'noplaylist': True,
    'cookiefile': 'cookies.txt'
}

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

        video_id = info.get('id', str(int(time.time())))
        url_cache[video_id] = url

        formats = info.get('formats', [])
        markup = InlineKeyboardMarkup()

        text = "<b>Available Video Streams:</b>\n<pre>"
        text += f"{'ID':<4} | {'Ext':<4} | {'Res':<9}\n"
        text += "-" * 22 + "\n"

        added = set()
        buttons = []

        for f in formats:
            height = f.get('height')
            vcodec = f.get('vcodec')
            ext = f.get('ext', 'unk')
            fid = f.get('format_id', 'N/A')

            if vcodec == 'none' or not height:
                continue

            res = f"{height}p"

            dynamic_range = f.get('dynamic_range', '')
            if dynamic_range and 'HDR' in str(dynamic_range).upper():
                res += " HDR"

            key = f"{res}_{ext}"

            if key not in added:
                added.add(key)

                text += f"{fid:<4} | {ext:<4} | {res:<9}\n"

                cb = f"dl|{video_id}|{fid}|{ext}"
                buttons.append(InlineKeyboardButton(f"{fid} ({res})", callback_data=cb))

        text += "</pre>\n<i>Select format:</i>"

        row = []
        for b in buttons:
            row.append(b)
            if len(row) == 2:
                markup.add(*row)
                row = []
        if row:
            markup.add(*row)

        markup.add(InlineKeyboardButton("🎵 Audio Only", callback_data=f"dl|{video_id}|bestaudio|m4a"))

        safe_edit(text, message.chat.id, status_msg.message_id, markup=markup, parse_mode='HTML')

except Exception as e:
    safe_edit(f"❌ Error: {e}", message.chat.id, status_msg.message_id)

@bot.callback_query_handler(func=lambda call: call.data.startswith('dl|'))
def handle_download(call):
_, video_id, format_id, req_ext = call.data.split('|')

url = url_cache.get(video_id)

safe_edit("⏳ Downloading...", call.message.chat.id, call.message.message_id)

if format_id == 'bestaudio':
    dl_format = 'bestaudio'
    merge_fmt = 'm4a'
else:
    dl_format = f"{format_id}+bestaudio/best"
    merge_fmt = 'mp4'

ydl_opts = {
    'format': dl_format,
    'outtmpl': f'downloads/{video_id}.%(ext)s',
    'cookiefile': 'cookies.txt',
    'quiet': True,
    'merge_output_format': merge_fmt
}

os.makedirs('downloads', exist_ok=True)

try:
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    files = glob.glob(f"downloads/{video_id}.*")
    file_path = files[0]

    safe_edit("📤 Uploading...", call.message.chat.id, call.message.message_id)

    with open(file_path, 'rb') as f:
        bot.send_document(call.message.chat.id, f)

    bot.delete_message(call.message.chat.id, call.message.message_id)
    os.remove(file_path)

except Exception as e:
    safe_edit(f"❌ Download error:\n{e}", call.message.chat.id, call.message.message_id)

print("Bot running...")

bot.infinity_polling()
