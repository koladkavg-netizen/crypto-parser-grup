import os
import requests
import time
import xml.etree.ElementTree as ET
import re
from flask import Flask
from threading import Thread

# --- 1. ВЕБ-СЕРВЕР ---
app = Flask('')

@app.route('/')
def home():
    return "Market Scanner AI: Diagnostic Mode Active"

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

FEEDS = [
    "https://forklog.com.ua/feed/",
    "https://incrypted.com/feed/",
    "https://itc.ua/news/feed/",
    "https://ru.beincrypto.com/feed/"
]

POSTED_NEWS = set()

# --- 3. АНАЛІТИКА З ДІАГНОСТИКОЮ ---
def translate_and_analyze(text):
    print(f"🧠 Аналіз новини: {text[:50]}...", flush=True)
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {"Authorization": f"Bearer {OR_KEY}", "Content-Type": "application/json"}
    
    prompt = (
        f"Ти — провідний український крипто-аналітик. Твоє завдання:\n"
        f"1. Якісно перекласти заголовок на українську.\n"
        f"2. Додати 1-2 речення глибокої аналітики (чому це важливо для ринку).\n"
        f"3. Текст має бути завершеним, БЕЗ обірваних слів.\n"
        f"4. Стиль: професійний, лаконічний.\n\n"
        f"Новина: {text}"
    )

    for attempt in range(3):
        try:
            res = requests.post(url, headers=headers, json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 400
            }, timeout=60)
            
            if res.status_code == 200:
                result = res.json()['choices'][0]['message']['content'].strip()
                
                # --- ДІАГНОСТИКА: дивимось, що прийшло ---
                print(f"🔍 [ДІАГНОСТИКА] Відповідь ШІ (довжина {len(result)}): {result[:150]}...", flush=True)
                
                # Перевіряємо, чи текст не занадто короткий і чи немає англійських артиклів
                if len(result) > 80 and not any(w in result.lower() for w in [' the ', ' is ', ' with ']):
                    return result
                else:
                    print("⚠️ Відхилено фільтром (закоротке або містить англійські слова)", flush=True)
            else:
                # --- ДІАГНОСТИКА: помилка API ---
                print(f"🛑 [ДІАГНОСТИКА] Помилка OpenRouter {res.status_code}: {res.text}", flush=True)
            
            print(f"⚠️ Спроба {attempt+1} невдала. Повтор...", flush=True)
            time.sleep(10)
        except Exception as e:
            print(f"❌ Помилка API: {e}", flush=True)
            time.sleep(5)
            
    return None

def send_to_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHANNEL_ID, "text": text, "parse_mode": "HTML", "disable_web_page_preview": False}
    try:
        res = requests.post(url, json=payload, timeout=20)
        return res.status_code == 200
    except:
        return False

# --- 4. ОСНОВНИЙ ЦИКЛ ---
def main_logic():
    print(f"\n🚀 --- ЗАПУСК МОНІТОРИНГУ: {time.strftime('%H:%M')} ---", flush=True)
    
    # Маскування під браузер
    req_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'
    }
    
    for feed_url in FEEDS:
        try:
            response = requests.get(feed_url, headers=req_headers, timeout=20)
            if response.status_code != 200:
                print(f"🛑 Сайт {feed_url} заблокував доступ (Помилка {response.status_code})", flush=True)
                continue
            
            root = ET.fromstring(response.content)
            item = root.find('.//item')
            if item is None: continue
            
            title = item.find('title').text
            link = item.find('link').text
            
            if title in POSTED_NEWS: continue
            
            final_text = translate_and_analyze(title)
            
            if final_text:
                post = f"<b>💎 MARKET SCANNER ANALYTICS</b>\n\n{final_text}\n\n🔗 <a href='{link}'>Джерело</a>"
                
                if send_to_telegram(post):
                    POSTED_NEWS.add(title)
                    print(f"✅ Опубліковано: {title[:30]}...", flush=True)
                    time.sleep(60)
            
        except Exception as e:
            print(f"⚠️ Помилка обробки {feed_url}: {e}", flush=True)

if __name__ == "__main__":
    print("🤖 Бот запущено в режимі ДІАГНОСТИКИ", flush=True)
    main_logic()
    
    while True:
        time.sleep
