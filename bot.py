#!/usr/bin/env python3
import os
import sqlite3
from config import TOKEN, ADMIN_ID, IMAGES_DIR, DB_PATH, ALLOWED_EXTENSIONS
from telegram import Update, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

class ImageBot:
    def __init__(self):
        os.makedirs(IMAGES_DIR, exist_ok=True)
        self.init_db()

    def init_db(self):
        """Initialize database with proper schema"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS images (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL UNIQUE,
                file_path TEXT NOT NULL
            )""")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_name ON images(name)")

    def find_image(self, name: str) -> str | None:
        """Find image path by name (without extension)"""
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT file_path FROM images WHERE name = ?", 
                (name.lower(),)
            )
            result = cursor.fetchone()
            return result[0] if result else None

    def save_image(self, name: str, file_path: str):
        """Save or update image record in database"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT OR REPLACE INTO images (name, file_path) VALUES (?, ?)",
                (name.lower(), file_path)
            )

    def get_actual_filename(self, base_name: str) -> str | None:
        """Check if file exists with any allowed extension"""
        for ext in ALLOWED_EXTENSIONS:
            filename = base_name.lower() + ext
            filepath = os.path.join(IMAGES_DIR, filename)
            if os.path.exists(filepath):
                return filename
        return None

    def handle_start(self, update: Update, context: CallbackContext):
        if update.effective_user.id == ADMIN_ID:
            update.message.reply_text(
                "🛠 Админ-команды:\n"
                "1. Отправь картинку с названием (без расширения)\n"
                "2. Существующие перезапишутся автоматически"
            )
        else:
            update.message.reply_text("🔍 Привет! Отправь название картинки (без расширения)")

    def handle_upload(self, update: Update, context: CallbackContext):
        """Handle image upload from admin"""
        if update.effective_user.id != ADMIN_ID:
            update.message.reply_text("🚫 Только для админа")
            return

        if not (update.message.photo or update.message.document):
            update.message.reply_text("❌ Отправьте изображение с названием")
            return

        base_name = (update.message.caption or "").strip().lower()
        if not base_name:
            update.message.reply_text("❌ Укажите название в подписи")
            return

        # Get file with highest resolution if it's a photo
        file_id = (update.message.photo[-1].file_id if update.message.photo 
                  else update.message.document.file_id)
        
        # Try all allowed extensions
        for ext in ALLOWED_EXTENSIONS:
            try:
                filename = base_name + ext
                filepath = os.path.join(IMAGES_DIR, filename)
                
                # Download file
                context.bot.get_file(file_id).download(filepath)
                
                # Update database
                self.save_image(base_name, filepath)
                
                update.message.reply_text(f"✅ Сохранено как: {filename}")
                return
            except Exception as e:
                continue

        update.message.reply_text("❌ Не удалось сохранить файл")

    def handle_request(self, update: Update, context: CallbackContext):
        """Handle image requests"""
        base_name = update.message.text.strip().lower()
        filepath = self.find_image(base_name)

        if filepath and os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                update.message.reply_photo(photo=InputFile(f))
        else:
            update.message.reply_text("❌ Изображение не найдено")

def main():
    bot = ImageBot()
    
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    # Handlers
    dp.add_handler(CommandHandler("start", bot.handle_start))
    dp.add_handler(MessageHandler(
        (Filters.photo | Filters.document) & Filters.chat(ADMIN_ID),
        bot.handle_upload
    ))
    dp.add_handler(MessageHandler(
        Filters.text & ~Filters.command,
        bot.handle_request
    ))

    print("🤖 Бот запущен!")
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
