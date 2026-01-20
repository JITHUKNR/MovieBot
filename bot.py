import os
import logging
import threading
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from pymongo import MongoClient
from bson.objectid import ObjectId  # ID വെച്ച് ഫയൽ കണ്ടുപിടിക്കാൻ
import re

# --- CONFIGURATION ---
TOKEN = os.environ.get("TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
ADMIN_ID = 7567364364  # നിങ്ങളുടെ ID

# --- WEB SERVER (Render-ന് വേണ്ടി) ---
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

# --- 1. SAVE FILE (ADMIN) ---
async def save_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    message = update.message
    file = message.document or message.video or message.audio
    
    if file:
        file_id = file.file_id
        # ഒറിജിനൽ പേര് എടുക്കുന്നു
        original_caption = message.caption or message.document.file_name or "Unknown Movie"
        
        # പേര് വൃത്തിയാക്കുന്നു (for Search)
        clean_name = re.sub(r"\[.*?\]|\(.*?\)", "", original_caption.replace(".", " ").replace("_", " ").replace("-", " "))
        clean_name = " ".join(clean_name.split())
        search_name = clean_name.lower()

        # Database-ൽ സേവ് ചെയ്യുന്നു
        files_col.update_one(
            {"file_unique_id": file.file_unique_id},
            {"$set": {
                "file_id": file_id, 
                "file_name": original_caption, # ബട്ടണിൽ കാണിക്കേണ്ട പേര്
                "search_name": search_name, 
                "file_type": "video"
            }},
            upsert=True
        )
        await update.message.reply_text(f"✅ **Saved!**\nSearch Name: `{search_name}`")

# --- 2. SEARCH MOVIE (WITH BUTTONS) ---
async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text.lower().strip()
    if len(user_query) < 2: return 

    status_msg = await update.message.reply_text(f"🔎 Searching for: **{user_query}**...")
    
    # സ്മാർട്ട് സെർച്ച് (Regex)
    query_parts = user_query.split()
    regex_pattern = ".*".join(query_parts)
    results = files_col.find({"search_name": {"$regex": regex_pattern}}).limit(10) # 10 എണ്ണം വരെ കാണിക്കും

    keyboard = []
    count = 0
    for file in results:
        count += 1
        # ബട്ടൺ ഉണ്ടാക്കുന്നു (പേര് + ID)
        # ID വളരെ വലുതാകാൻ പാടില്ല, അതുകൊണ്ട് database ID (_id) ഉപയോഗിക്കുന്നു
        btn_text = f"🎬 {file['file_name'][:30]}..." # പേര് നീളം കൂടിയാൽ ചുരുക്കും
        callback_data = f"dl_{str(file['_id'])}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback_data)])

    if count == 0:
        await status_msg.edit_text("❌ **Not Found!**\nPlease check the spelling.")
    else:
        await status_msg.edit_text(
            f"✅ **Found {count} Movies!**\nSelect one to download: 👇",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

# --- 3. BUTTON CLICK HANDLER (ഫയൽ അയക്കാൻ) ---
async def send_movie_by_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer() # ലോഡിംഗ് നിർത്താൻ

    data = query.data
    if data.startswith("dl_"):
        # ID വേർതിരിച്ചെടുക്കുന്നു
        file_oid = data.split("_")[1]
        
        try:
            # Database-ൽ നിന്ന് ഫയൽ എടുക്കുന്നു
            file_data = files_col.find_one({"_id": ObjectId(file_oid)})
            
            if file_data:
                await query.message.reply_document(
                    document=file_data['file_id'],
                    caption=f"🎬 **{file_data['file_name']}**\n🤖 Uploaded by SNAFLIX"
                )
            else:
                await query.message.reply_text("❌ File removed or not found.")
        except Exception as e:
            await query.message.reply_text("❌ Error fetching file.")
            logging.error(f"Error: {e}")

# --- MAIN ---
def main():
    if not TOKEN: return

    # വെബ് സെർവർ റൺ ചെയ്യുന്നു
    threading.Thread(target=run_web_server, daemon=True).start()

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, save_file))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie))
    
    # ബട്ടൺ ക്ലിക്ക് ചെയ്യുമ്പോൾ പ്രവർത്തിക്കാൻ
    app.add_handler(CallbackQueryHandler(send_movie_by_button))

    print("Movie Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
