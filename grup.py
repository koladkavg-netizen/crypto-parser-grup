import os
import requests
import time
import xml.etree.ElementTree as ET
import re

# --- КОНФІГУРАЦІЯ (Беремо з Environment Variables на Render) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.getenv("TELEGRAM_CHANNEL_ID")
OR_KEY = os.getenv("OPENROUTER_API_KEY")

# Список RSS-фідів
FEEDS = [
    "https://forklog.com.ua/feed/",
    "https://incrypted.com/feed/",
    "https://itc.ua/news/feed/",
    "https://bits.media/rss/",
    "https://ru.beincrypto.com/feed/" # Він часто дає англійською або російською
]

# Файл для історії (на Render він буде скидатися при рестарті, 
# але в циклі while True база триматиметься в пам'яті)
POSTED_NEWS = set()

def translate_news(text):
    """Переклад через OpenRouter (Gemini 2.0 Flash) з перевірками"""
    print("🔄 Запуск перекладу...")
    
    # Очищуємо текст від зайвих тегів та обрізаємо довжину
    clean_text = re.sub(r'<[^>]+>', '', text)[:1200] 

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OR_KEY}",
        "Content-Type": "application/json"
    }
    
    prompt = f"Ти професійний крипто-журналіст. Переклади цей текст на УКРАЇНСЬКУ мову. Пиши стисло, професійно, використовуй крипто-терміни. Не додавай фрази типу 'Ось ваш переклад'.\n\nТекст:\n{clean_text}"

    for i in range(3): # 3 спроби
        try:
            res = requests.post(url, headers=headers, json={
                "model": "google/gemini-2.0-flash-001",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4
            }, timeout=40)
            
            if res.status_code == 200:
                translated = res.json()['choices'][0]['message']['content'].strip()
                
                # Перевірка на англійську (якщо лишилися артиклі - значить не переклав)
                bad_words = [' the ', ' is ', ' with ', ' that ']
                if not any(word in translated.lower() for word in bad_words):
                    return translated
                else:
                    print(f"⚠️ Спроба {i+1}: Отримано неякісний переклад (схоже на англійську).")
            else:
                print(f"⚠️ Помилка API {res.status_code}: {res.text}")
        except Exception as e:
            print(f"⚠️ Помилка мережі при перекладі: {e}")
        
        time.sleep(5) # Пауза перед повторною спробою
    
    return None

def send_to_telegram(text):
    """Відправка готового тексту в канал"""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    try:
        res = requests.post(url, json=payload)
        return res.status_code == 200
    except Exception as e:
        print(f"❌ Помилка відправки в TG: {e}")
        return False

def parse_and_post():
    """Основна логіка парсингу"""
    print(f"\n--- ПЕРЕВІРКА НОВИН: {time.strftime('%H:%M:%S')} ---")
    
    for feed_url in FEEDS:
        try:
            response = requests.get(feed_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=20)
            if response.status_code != 200: continue
            
            root = ET.fromstring(response.content)
            for item in root.findall('.//item')[:3]: # Беремо останні 3 новини з кожного фіда
                title = item.find('title').text
                link = item.find('link').text
                
                # Якщо новина вже була — пропускаємо
                if title in POSTED_NEWS:
                    continue
                
                print(f"🆕 Нова новина: {title}")
                
                # Перекладаємо
                translated_text = translate_news(title)
                
                if translated_text:
                    # Формуємо пост
                    post_text = f"<b>🔔 НОВИНА</b>\n\n{translated_text}\n\n👉 <a href='{link}'>Читати першоджерело</a>"
                    
                    if send_to_telegram(post_text):
                        print("✅ Опубліковано в Telegram!")
                        POSTED_NEWS.add(title)
                        # Пауза між постами (якщо їх декілька), щоб не спамити
                        time.sleep(10)
                else:
                    print(f"❌ Не вдалося перекласти новину: {title}")
                    
        except Exception as e:
            print(f"⚠️ Помилка парсингу {feed_url}: {e}")

if __name__ == "__main__":
    print("🚀 ПАРСЕР ЗАПУЩЕНО")
    
    # Нескінченний цикл для роботи на Render
    while True:
        try:
            parse_and_post()
        except Exception as e:
            print(f"☢️ КРИТИЧНИЙ ЗБІЙ ЦИКЛУ: {e}")
        
        # Перевірка кожні 15 хвилин (900 секунд)
        print("\n😴 Сплю 15 хвилин...")
        time.sleep(900)
