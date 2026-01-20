import os
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient
import re

# --- CONFIGURATION ---
TOKEN = os.environ.get("TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
ADMIN_ID = 7567364364  # നിങ്ങളുടെ ID

# --- WEB SERVER FOR RENDER (ഇതാണ് പുതിയ മാറ്റം!) ---
# Render-നെ പറ്റിക്കാൻ ഒരു ചെറിയ വെബ്സൈറ്റ്
app_web = Flask(__name__)

@app_web.route('/')
def home():
    return "Movie Bot is Running Successfully! 🚀"

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app_web.run(host='0.0.0.0', port=port)

# --- DATABASE CONNECTION ---
client = MongoClient(MONGO_URI)
db = client["MovieBot"]
files_col = db["files"]

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id == ADMIN_ID:
        await update.message.reply_text(
            f"👋 **Welcome Boss!** 😎\nForward movie files here to save them."
        )
    else:
        await update.message.reply_text(
            f"👋 **Hello {user.first_name}!**\nType a Movie Name to search.\nExample: *Lucifer*, *Premam*"
        )

# --- SAVE FILE (ADMIN) ---
async def save_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    message = update.message
    file = message.document or message.video or message.audio
    if file:
        file_id = file.file_id
        original_caption = message.caption or message.document.file_name or "Unknown Movie"
        
        # Cleaning Name
        clean_name = re.sub(r"\[.*?\]|\(.*?\)", "", original_caption.replace(".", " ").replace("_", " ").replace("-", " "))
        clean_name = " ".join(clean_name.split())
        search_name = clean_name.lower()

        files_col.update_one(
            {"file_unique_id": file.file_unique_id},
            {"$set": {"file_id": file_id, "file_name": original_caption, "search_name": search_name, "file_type": "video"}},
            upsert=True
        )
        await update.message.reply_text(f"✅ **Saved!**\nSearch Name: `{search_name}`")

# --- SEARCH MOVIE (USER) ---
async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text.lower().strip()
    if len(user_query) < 2: return 
    await update.message.reply_text(f"🔎 Searching for: **{user_query}**...")
    
    query_parts = user_query.split()
    regex_pattern = ".*".join(query_parts)
    results = files_col.find({"search_name": {"$regex": regex_pattern}})
    
    count = 0
    for file in results:
        try:
            await update.message.reply_document(document=file['file_id'], caption=f"🎬 **{file['file_name']}**\n🤖 Uploaded by SNAFLIX")
            count += 1
            if count >= 5: break 
        except Exception as e:
            logging.error(f"Error: {e}")

    if count == 0:
        await update.message.reply_text("❌ **Not Found!**\nTry checking the spelling.")

# --- MAIN ---
def main():
    if not TOKEN: return

    # വെബ് സെർവർ ബാക്ക്ഗ്രൗണ്ടിൽ റൺ ചെയ്യുന്നു
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, save_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie))

    print("Movie Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
