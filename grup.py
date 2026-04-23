import os
import requests
import time
import xml.etree.ElementTree as ET
import re
from flask import Flask
from threading import Thread

# --- 1. ПРАВИЛЬНИЙ FLASK ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Market Scanner AI is alive and running!"

def run():
    # Render автоматично надає порт через змінну оточення PORT
    # Якщо її немає, використовуємо 10000 (стандарт для Render)
    port = int(os.environ.get("PORT", 10000))
    print(f"📡 Flask сервер запускається на порту {port}...")
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True # Це важливо: потік помре разом з основною програмою
    t.start()

# --- 2. КОНФІГУРАЦІЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

FEEDS = [
    "https://forklog.com.ua/feed/",
    "https://incrypted.com/feed/",
    "https://itc.ua/news/feed/",
    "https://bits.media/rss/",
    "https://ru.beincrypto.com/feed/"
]

POSTED_NEWS = set()

# --- 3. ЛОГІКА ПЕРЕКЛАДУ ---
def translate_news(text):
    print(f"🔄 Запит на переклад: {text[:50]}...")
    clean_text = re.sub(r'<[^>]+>', '', text)[:1200] 
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OR_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = (
        "Ти професійний крипто-журналіст. Переклади цей текст на УКРАЇНСЬКУ мову. "
        "Пиши стисло, професійно. Не використовуй фрази 'Ось переклад'. "
        f"Текст:\n{clean_text}"
    )

    for attempt in range(3):
        try:
            res = requests.post(url, headers=headers, json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }, timeout=45)
            
            if res.status_code == 200:
                translated = res.json()['choices'][0]['message']['content'].strip()
                if not any(word in translated.lower() for word in [' the ', ' is ', ' with ', ' and ']):
                    return translated
            print(f"⚠️ Спроба {attempt+1} не вдалася.")
        except Exception as e:
            print(f"⚠️ Збій: {e}")
        time.sleep(5)
    return None

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.status_code == 200
    except:
        return False

def parse_and_post():
    print(f"\n--- ПЕРЕВІРКА НОВИН: {time.strftime('%H:%M:%S')} ---")
    for feed_url in FEEDS:
        try:
            response = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
            if response.status_code != 200: continue
            root = ET.fromstring(response.content)
            for item in root.findall('.//item')[:3]:
                title = item.find('title').text
                link = item.find('link').text
                if title in POSTED_NEWS: continue
                
                translated_text = translate_news(title)
                if translated_text:
                    final_post = f"<b>🔔 НОВИНА</b>\n\n{translated_text.strip()}\n\n👉 <a href='{link}'>Джерело</a>"
                    if send_to_telegram(final_post):
                        print(f"✅ Опубліковано: {title[:30]}")
                        POSTED_NEWS.add(title)
                        time.sleep(10)
        except Exception as e:
            print(f"⚠️ Помилка: {e}")

# --- 4. ЗАПУСК ---
if __name__ == "__main__":
    # СПОЧАТКУ запускаємо сервер для Render
    keep_alive()
    
    # Даємо Flask пару секунд, щоб порт точно відкрився
    time.sleep(3)
    
    print("🚀 БОТ-ПАРСЕР ЗАПУЩЕНО")
    
    while True:
        try:
            parse_and_post()
        except Exception as e:
            print(f"☢️ Помилка циклу: {e}")
        
        print("\n😴 Сплю 15 хвилин...")
        time.sleep(900)
