import os
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes

TOKEN = "8731814924:AAGx2vfmMc00ywb0erHTFq3KsbmHBiOjHBM"

async def download(update: Update, context: ContextTypes.DEFAULT_TYPE):

    url = update.message.text

    msg = await update.message.reply_text("Starting download...")

    def progress_hook(d):
        if d['status'] == 'downloading':
            percent = d.get('_percent_str', '').strip()
            speed = d.get('_speed_str', '').strip()
            size = d.get('_total_bytes_str', '').strip()

            text = f"Downloading...\n{percent}\nSpeed: {speed}\nSize: {size}"

            try:
                context.application.create_task(
                    msg.edit_text(text)
                )
            except:
                pass

        if d['status'] == 'finished':
            context.application.create_task(
                msg.edit_text("Download finished. Uploading...")
            )

    ydl_opts = {
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "outtmpl": "video.%(ext)s",
        "progress_hooks": [progress_hook],
        "cookiefile": "cookies.txt"
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    for file in os.listdir():
        if file.startswith("video"):
            await update.message.reply_video(video=open(file, "rb"))
            os.remove(file)

app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), download))

app.run_polling()