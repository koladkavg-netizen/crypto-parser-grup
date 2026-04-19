import os
import feedparser
import requests
import sqlite3
import time
import threading
from datetime import datetime
from deep_translator import GoogleTranslator
from flask import Flask

# ================= МІНІ-ВЕБ-СЕРВЕР ДЛЯ КРОНА =================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running! 🚀", 200

def run_web_server():
    # Render передає порт через змінну оточення PORT
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ================= НАЛАШТУВАННЯ БОТА =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")

THREADS = {
    "news": 7, "analytics": 9, "onchain": 11, "web3": 13, "ua": 15
}

SOURCES = [
    {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss", "thread": THREADS["news"]},
    {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/", "thread": THREADS["news"]},
    {"name": "CryptoSlate", "url": "https://cryptoslate.com/feed/", "thread": THREADS["news"]},
    {"name": "BeInCrypto", "url": "https://beincrypto.com/feed/", "thread": THREADS["news"]},
    {"name": "Incrypted", "url": "https://incrypted.com/feed/", "thread": THREADS["ua"]},
    {"name": "ForkLog UA", "url": "https://forklog.com.ua/feed", "thread": THREADS["ua"]}
]

# ... (тут функція init_db, is_posted, mark_as_posted, translate_to_ukrainian такі ж, як були) ...
def init_db():
    conn = sqlite3.connect("crypto_news.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS posted_news (link TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()

def is_posted(link):
    conn = sqlite3.connect("crypto_news.db")
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM posted_news WHERE link = ?", (link,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def mark_as_posted(link):
    conn = sqlite3.connect("crypto_news.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO posted_news (link) VALUES (?)", (link,))
    conn.commit()
    conn.close()

def translate_to_ukrainian(text):
    try:
        return GoogleTranslator(source='auto', target='uk').translate(text)
    except:
        return text

def send_to_telegram(text, thread_id):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {"chat_id": GROUP_CHAT_ID, "message_thread_id": thread_id, "text": text, "parse_mode": "HTML"}
    while True:
        r = requests.post(url, json=payload).json()
        if r.get("ok"): return True
        if r.get("error_code") == 429:
            time.sleep(r['parameters']['retry_after'] + 1)
        else: return False

def run_parser():
    while True:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Перевірка новин...")
        for source in SOURCES:
            try:
                feed = feedparser.parse(source["url"])
                for entry in feed.entries[:2]:
                    if not is_posted(entry.link):
                        title = translate_to_ukrainian(entry.title)
                        msg = f"📰 <b>{source['name']}</b>\n\n🔹 {title}\n\n👉 <a href='{entry.link}'>Читати</a>"
                        if send_to_telegram(msg, source["thread"]):
                            mark_as_posted(entry.link)
                            print(f"✅ ОК: {title[:30]}...")
                            time.sleep(3)
            except Exception as e: print(f"Error: {e}")
        time.sleep(600)

if __name__ == "__main__":
    init_db()
    # ЗАПУСКАЄМО ВЕБ-СЕРВЕР У ОКРЕМОМУ ПОТОЦІ
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🤖 Бот та Веб-сервер запущені!")
    run_parser()
