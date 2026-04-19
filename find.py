import requests

TOKEN = "8682834780:AAFA2LNrbqrygTkkdbLhOZwy9nPShAsnZvo"
CHAT_ID = "-1003749922724"

print("🚀 Починаємо сканувати всі можливі номери гілок (від 1 до 50)...")

for i in range(1, 50):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "message_thread_id": i,
        "text": f"✅ Це тестове повідомлення! Справжній ID цієї гілки: {i}"
    }
    
    # Відправляємо запит
    response = requests.post(url, json=payload).json()
    
    # Якщо Telegram відповів "ОК"
    if response.get("ok"):
        print(f"✅ БІНГО! Гілка з ID {i} існує!")