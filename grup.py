import os
import requests
import time
import xml.etree.ElementTree as ET
import re
from flask import Flask
from threading import Thread

# --- 1. ПРЯМИЙ ЗАПУСК FLASK (для Render) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    # Render автоматично підставляє PORT. Якщо ні - беремо 8080
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

# Запускаємо сервер у фоновому потоці ВІДРАЗУ
t = Thread(target=run)
t.daemon = True
t.start()

# --- 2. КОНФІГУРАЦІЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

FEEDS = [
    "https://forklog.com.ua/feed/",
    "https://incrypted.com/feed/",
    "https://itc.ua/news/feed/",
    "https://ru.beincrypto.com/feed/"
]

POSTED_NEWS = set()

# --- 3. ЛОГІКА ПЕРЕКЛАДУ ---
def translate_news(text):
    print(f"🔄 Переклад: {text[:40]}...")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
    
    prompt = f"Ти професійний крипто-журналіст. Переклади це на УКРАЇНСЬКУ мову. Пиши коротко і професійно. Текст:\n{text}"

    for i in range(3): # 3 спроби
        try:
            res = requests.post(url, headers=headers, json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }, timeout=30)
            
            if res.status_code == 200:
                translated = res.json()['choices'][0]['message']['content'].strip()
                # Перевірка, щоб не було англійської
                if not any(word in translated.lower() for word in [' the ', ' is ', ' and ']):
                    return translated
        except:
            time.sleep(2)
    return None

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML"}
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.status_code == 200
    except:
        return False

# --- 4. ОСНОВНИЙ ЦИКЛ ---
def parse_and_post():
    print(f"🔍 Перевірка новин... {time.strftime('%H:%M')}")
    for feed_url in FEEDS:
        try:
            response = requests.get(feed_url, timeout=15)
            root = ET.fromstring(response.content)
            for item in root.findall('.//item')[:2]:
                title = item.find('title').text
                link = item.find('link').text
                
                if title in POSTED_NEWS: continue
                
                translated = translate_news(title)
                if translated:
                    post = f"<b>🔔 НОВИНА</b>\n\n{translated}\n\n👉 <a href='{link}'>Джерело</a>"
                    if send_to_telegram(post):
                        POSTED_NEWS.add(title)
                        print("✅ Опубліковано!")
                        time.sleep(5)
        except Exception as e:
            print(f"⚠️ Помилка: {e}")

if __name__ == "__main__":
    print("🚀 БОТ ЗАПУЩЕНИЙ")
    while True:
        parse_and_post()
        time.sleep(600) # Кожні 10 хв
