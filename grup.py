import os
import feedparser
import requests
import sqlite3
import time
import threading
from datetime import datetime
from flask import Flask

# ================= МІНІ-ВЕБ-СЕРВЕР ДЛЯ КРОНА =================
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running! 🚀", 200

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

# ================= НАЛАШТУВАННЯ БОТА =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_CHAT_ID = os.getenv("GROUP_CHAT_ID")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY") # НОВИЙ КЛЮЧ ДЛЯ ШІ

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

# ================= ПЕРЕКЛАД ЧЕРЕЗ ШІ (OPENROUTER) =================
def translate_with_ai(text):
    if not OPENROUTER_API_KEY:
        print("⚠️ Увага: OPENROUTER_API_KEY не знайдено. Повертаю оригінальний текст.")
        return text

    prompt = f"""Ти — досвідчений криптоаналітик. Твоє завдання: перекласти заголовок новини українською мовою. 
    Переклад має бути адаптований для професійної крипто-спільноти. Використовуй правильну термінологію (наприклад, бичачий/ведмежий ринок, халвінг, кити, ліквідність).
    Видай ТІЛЬКИ ідеально перекладений текст, без жодних вступних слів, без пояснень і без лапок.
    
    Оригінал: '{text}'"""

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=20
        )
        
        if response.status_code == 200:
            translated_text = response.json()['choices'][0]['message']['content'].strip()
            # Додаткова зачистка від випадкових лапок, які ШІ іноді любить залишати
            translated_text = translated_text.strip("'\"")
            return translated_text
        else:
            print(f"⚠️ Помилка OpenRouter: Код {response.status_code}")
            return text
    except Exception as e:
        print(f"⚠️ Помилка з'єднання з ШІ: {e}")
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
                        # Використовуємо ШІ для перекладу
                        title = translate_with_ai(entry.title)
                        
                        msg = f"📰 <b>{source['name']}</b>\n\n🔹 {title}\n\n👉 <a href='{entry.link}'>Читати</a>"
                        if send_to_telegram(msg, source["thread"]):
                            mark_as_posted(entry.link)
                            print(f"✅ ОК: {title[:30]}...")
                            time.sleep(3)
            except Exception as e: 
                print(f"Error parsing {source['name']}: {e}")
        time.sleep(600)

if __name__ == "__main__":
    init_db()
    # ЗАПУСКАЄМО ВЕБ-СЕРВЕР У ОКРЕМОМУ ПОТОЦІ
    threading.Thread(target=run_web_server, daemon=True).start()
    print("🤖 Бот та Веб-сервер запущені!")
    run_parser()
