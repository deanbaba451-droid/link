import telebot
import os
import sqlite3
import time
from threading import Thread
from flask import Flask

# --- AYARLAR ---
TOKEN = "8660550338:AAG6UPjuMWKV0RWnJVr-D51uuF_MuaW3F9M"
TARGET_CHAT_ID = -1004429335198
OWNER_ID = 8813586213
CUSTOM_EMOJI_ID = "5451732530048802485"

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- VERİTABANI İŞLEMLERİ ---
DB_NAME = "bot_data.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS join_requests (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            username TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def save_user(user_id, first_name, username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR IGNORE INTO join_requests (user_id, first_name, username, timestamp)
        VALUES (?, ?, ?, datetime('now'))
    """, (user_id, first_name, username))
    conn.commit()
    conn.close()

def get_all_user_ids():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM join_requests")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

def format_user_display(user_id, first_name, username=None):
    """Kullanıcı adı varsa gösterir, yoksa first_name ile tg://user linki oluşturur."""
    display_name = first_name if first_name else "kullanıcı"
    safe_name = display_name.replace("<", "&lt;").replace(">", "&gt;")
    
    if username:
        return f'<a href="https://t.me/{username}">@{username}</a> (<code>{user_id}</code>)'
    else:
        return f'<a href="tg://user?id={user_id}">{safe_name}</a> (<code>{user_id}</code>)'

# --- WEB SUNUCUSU ---
@app.route('/')
def home():
    return "bot aktif ve çalışıyor"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)

# --- BOT HANDLERLARI ---

# 1. Gruba Katılma İsteği Atıldığında
@bot.chat_join_request_handler()
def handle_join_request(request: telebot.types.ChatJoinRequest):
    if request.chat.id == TARGET_CHAT_ID:
        user_id = request.from_user.id
        first_name = request.from_user.first_name
        username = request.from_user.username
        group_name = request.chat.title.lower()
        
        # Veritabanına kaydet
        save_user(user_id, first_name, username)
        
        # Kullanıcıya giden mesaj
        welcome_text = (
            f"<b>{group_name}</b> grubuna hoş geldin, main grubumuza istek atmayı unutma. "
            f'<tg-emoji emoji-id="{CUSTOM_EMOJI_ID}">⏳</tg-emoji>\n\n'
            f"<b>https://t.me/+O8G59D_h39gyZWJh</b>"
        )
        
        try:
            bot.send_message(user_id, welcome_text, parse_mode="HTML")
        except Exception as e:
            print(f"kullanıcıya mesaj gönderilemedi ({user_id}): {e}")
            
        # Kurucuya giden anlık bildirim
        user_fmt = format_user_display(user_id, first_name, username)
        owner_notify_text = f"yeni katılım isteği:\n• {user_fmt}"
        
        try:
            bot.send_message(OWNER_ID, owner_notify_text, parse_mode="HTML")
        except Exception as e:
            print(f"owner anlık bildirim hatası: {e}")

# 2. Kurucu Duyuru Komutu
@bot.message_handler(commands=['duyuru'])
def handle_duyuru(message: telebot.types.Message):
    if message.from_user.id != OWNER_ID:
        return
    
    msg_text = message.text.replace("/duyuru", "").strip()
    if not msg_text:
        bot.reply_to(message, "lütfen duyuru metnini girin.\nörnek: <code>/duyuru merhaba herkese!</code>", parse_mode="HTML")
        return
    
    all_users = get_all_user_ids()
    success = 0
    failed = 0
    
    status_msg = bot.reply_to(message, f"duyuru gönderiliyor... (toplam: {len(all_users)} kullanıcı)")
    
    for uid in all_users:
        try:
            bot.send_message(uid, msg_text, parse_mode="HTML")
            success += 1
            time.sleep(0.05)
        except Exception:
            failed += 1
            
    bot.edit_message_text(
        f"duyuru tamamlandı.\n\nbaşarılı: {success}\nbaşarısız: {failed}",
        chat_id=message.chat.id,
        message_id=status_msg.message_id,
        parse_mode="HTML"
    )

# 3. Kullanıcılar Bota Özel Mesaj Yazdığında Kurucuya İlet
@bot.message_handler(func=lambda message: message.chat.type == "private")
def forward_user_message(message: telebot.types.Message):
    if message.from_user.id == OWNER_ID:
        return
    
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    username = message.from_user.username
    
    user_fmt = format_user_display(user_id, first_name, username)
    info_header = f"yeni kullanıcı mesajı:\n• {user_fmt}\n\n"
    
    try:
        bot.send_message(OWNER_ID, info_header, parse_mode="HTML")
        bot.forward_message(OWNER_ID, message.chat.id, message.message_id)
    except Exception as e:
        print(f"mesaj iletme hatası: {e}")

if __name__ == "__main__":
    init_db()
    
    Thread(target=run_web, daemon=True).start()
    
    print("bot aktif...")
    bot.infinity_polling()
