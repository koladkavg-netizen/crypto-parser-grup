import os
import requests
import time
import xml.etree.ElementTree as ET
import re
from flask import Flask
from threading import Thread

# --- 1. ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask('')

@app.route('/')
def home():
    return "Market Scanner AI: High-Quality Mode Active"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

t = Thread(target=run)
t.daemon = True
t.start()

# --- 2. КОНФІГУРАЦІЯ ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

# Джерела новин
FEEDS = [
    "https://forklog.com.ua/feed/",
    "https://incrypted.com/feed/",
    "https://itc.ua/news/feed/",
    "https://ru.beincrypto.com/feed/"
]

POSTED_NEWS = set()

# --- 3. ГЛИБОКА АНАЛІТИКА ТА ПЕРЕКЛАД ---
def translate_and_analyze(text):
    print(f"🧠 Глибокий аналіз новини: {text[:50]}...")
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OR_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://render.com", # Для OpenRouter
    }
    
    # Жорсткий промпт для якості
    prompt = (
        f"Ти — провідний український крипто-аналітик. Твоє завдання:\n"
        f"1. Якісно перекласти заголовок на українську.\n"
        f"2. Додати 1-2 речення глибокої аналітики (чому це важливо для ринку).\n"
        f"3. Текст має бути завершеним, БЕЗ обірваних слів.\n"
        f"4. Стиль: професійний, лаконічний.\n\n"
        f"Новина для обробки: {text}"
    )

    for attempt in range(3):
        try:
            # Використовуємо Gemini Flash, але з підвищеними параметрами для якості
            res = requests.post(url, headers=headers, json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4, # Менше творчості, більше точності
                "max_tokens": 400
            }, timeout=60) # Даємо ШІ цілу хвилину на роздуми
            
            if res.status_code == 200:
                result = res.json()['choices'][0]['message']['content'].strip()
                
                # Валідація: якщо текст занадто короткий або є англійські слова — це брак
                bad_words = [' the ', ' is ', ' with ', ' analysis ']
                if len(result) > 80 and not any(w in result.lower() for w in bad_words):
                    return result
            
            print(f"⚠️ Спроба {attempt+1} не пройшла валідацію якості. Переробляю...")
            time.sleep(10) # Пауза перед повторною спробою
        except Exception as e:
            print(f"❌ Помилка API: {e}")
            time.sleep(5)
            
    return None

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID, 
        "text": text, 
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.status_code == 200
    except:
        return False

# --- 4. ОСНОВНИЙ ЦИКЛ З ТОРМОЗАМИ ---
def main_logic():
    print(f"\n🚀 --- ЗАПУСК МОНІТОРИНГУ: {time.strftime('%H:%M')} ---")
    
    for feed_url in FEEDS:
        try:
            response = requests.get(feed_url, timeout=20)
            if response.status_code != 200: continue
            
            root = ET.fromstring(response.content)
            # БЕРЕМО ТІЛЬКИ 1 ОСТАННЮ НОВИНУ (якість понад кількість)
            item = root.find('.//item')
            if item is None: continue
            
            title = item.find('title').text
            link = item.find('link').text
            
            if title in POSTED_NEWS: continue
            
            # Обробка ШІ
            final_text = translate_and_analyze(title)
            
            if final_text:
                post = (
                    f"<b>💎 MARKET SCANNER ANALYTICS</b>\n\n"
                    f"{final_text}\n\n"
                    f"🔗 <a href='{link}'>Джерело новини</a>"
                )
                
                if send_to_telegram(post):
                    POSTED_NEWS.add(title)
                    print(f"✅ Опубліковано якісний пост: {title[:30]}...")
                    
                    # ПАУЗА 1 ХВИЛИНА між постами з різних джерел
                    print("😴 Пауза 60 сек для стабільності...")
                    time.sleep(60)
            
        except Exception as e:
            print(f"⚠️ Помилка обробки {feed_url}: {e}")

if __name__ == "__main__":
    print("🤖 Бот запущено в режимі ВИСОКОЇ ЯКОСТІ")
    
    # Перший запуск відразу
    main_logic()
    
    while True:
        # Перевірка кожні 15 хвилин
        time.sleep(900)
        try:
            main_logic()
        except Exception as e:
            print(f"☢️ Збій: {e}")
