import os
import aiohttp
import asyncio
from tasks.celery_app import app
from dotenv import load_dotenv

load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

@app.task
def send_message(chat_id, message):
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }
    
    async def send_async():
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(BASE_URL, json=payload) as response:
                    if response.status != 200:
                        print(f"Ошибка {response.status} при отправке пользователю {chat_id}")
                    else:
                        print(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            print(f"Ошибка при отправке пользователю {chat_id}: {e}")

    asyncio.run(send_async())
