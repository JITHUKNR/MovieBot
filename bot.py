import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from pymongo import MongoClient
import re

# --- CONFIGURATION ---
# Render-ൽ കൊടുക്കുന്ന വേരിയബിളുകൾ
TOKEN = os.environ.get("TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")

# ⚠️ നിങ്ങളുടെ ID ഇവിടെ മാറ്റാൻ മറക്കല്ലേ!
ADMIN_ID = 7567364364 

# --- DATABASE CONNECTION ---
client = MongoClient(MONGO_URI)
db = client["MovieBot"]  # Database പേര് വേണമെങ്കിൽ മാറ്റാം
files_col = db["files"]

# --- LOGGING ---
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# --- START COMMAND ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎬 **Movie Finder Bot Ready!**\n\n"
        "To get a movie, just type its name.\n"
        "(Example: *Lucifer*, *Premam*)\n\n"
        "⚠️ **Admin Note:** First, forward movie files here to save them."
    )

# --- 1. ADMIN SAVING FILES (അഡ്മിൻ ഫയൽ സേവ് ചെയ്യുന്നു) ---
async def save_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # അഡ്മിൻ അല്ലെങ്കിൽ ഒന്നും ചെയ്യില്ല
    if update.effective_user.id != ADMIN_ID:
        return

    message = update.message
    # വീഡിയോയോ ഓഡിയോയോ ഡോക്യുമെന്റോ ആണോ എന്ന് നോക്കുന്നു
    file = message.document or message.video or message.audio
    
    if file:
        file_id = file.file_id
        # ഫയലിന്റെ പേര് എടുക്കുന്നു
        original_caption = message.caption or ""
        file_name = message.document.file_name if message.document else (original_caption or "Unknown Movie")
        
        # സേവ് ചെയ്യാനുള്ള പേര് (Caption ഉണ്ടെങ്കിൽ അത്, ഇല്ലെങ്കിൽ File Name)
        final_name = original_caption if original_caption else file_name
        
        # സെർച്ച് ചെയ്യാൻ എളുപ്പത്തിന് എല്ലാം ചെറിയ അക്ഷരമാക്കുന്നു
        search_name = final_name.lower().replace("_", " ").replace(".", " ")

        # ഡാറ്റാബേസിലേക്ക്റ്റുന്നു
        files_col.update_one(
            {"file_unique_id": file.file_unique_id},
            {"$set": {
                "file_id": file_id, 
                "file_name": final_name, 
                "search_name": search_name,
                "file_type": "video"
            }},
            upsert=True
        )
        
        await update.message.reply_text(f"✅ **Saved to Database!**\n📂 Name: {final_name}")

# --- 2. USER SEARCHING (യൂസർ സിനിമ ചോദിക്കുന്നു) ---
async def search_movie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_query = update.message.text.lower().strip()
    
    # 3 അക്ഷരത്തിൽ കുറവാണെങ്കിൽ മറുപടി വേണ്ട
    if len(user_query) < 2:
        return 

    await update.message.reply_text(f"🔎 Searching for: **{user_query}**...")
    
    # Regex ഉപയോഗിച്ച് സെർച്ച് ചെയ്യുന്നു
    results = files_col.find({"search_name": {"$regex": user_query}})
    
    count = 0
    for file in results:
        try:
            await update.message.reply_document(
                document=file['file_id'],
                caption=f"🎬 **{file['file_name']}**\n🤖 Uploaded by Movie Bot"
            )
            count += 1
            if count >= 3: break # പരമാവധി 3 എണ്ണം അയക്കും
        except Exception as e:
            logging.error(f"Error: {e}")

    if count == 0:
        await update.message.reply_text("❌ **Not Found!**\nഈ സിനിമ ഇതുവരെ അപ്‌ലോഡ് ചെയ്തിട്ടില്ല.")

# --- MAIN ---
def main():
    if not TOKEN:
        print("Error: TOKEN not found!")
        return

    app = Application.builder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    
    # ഫയൽ വന്നാൽ സേവ് ചെയ്യും (Admin Only)
    app.add_handler(MessageHandler(filters.Document.ALL | filters.VIDEO | filters.AUDIO, save_file))
    
    # ടെക്സ്റ്റ് വന്നാൽ സെർച്ച് ചെയ്യും (All Users)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search_movie))

    print("Movie Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
