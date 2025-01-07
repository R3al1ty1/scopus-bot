import os
import asyncio
import aiohttp
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Chat
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB-USER')}:{os.getenv('DB-PASSWORD')}@{os.getenv('DB-HOST')}:{os.getenv('DB-PORT')}/{os.getenv('DB-NAME')}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

BOT_TOKEN = os.getenv('BOT_TOKEN')
MESSAGE = """🎉 Поздравляем всех с наступившим 2025 годом! 

⚙️ Важная информация: Scopus изменил порядок авторизации, из-за чего бот может выдавать неверные результаты. В связи с этим мы полностью переписываем техническую логику бота.

⏳ Работа бота будет приостановлена на 2-3 дня.

💬 Приносим извинения за неудобства! Если у вас возникли ошибки в запросах, пожалуйста, напишите в поддержку — мы компенсируем любые потери, чтобы вы могли использовать обновленного бота в будущем!

🙏 Спасибо за ваше понимание!"""
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

async def send_message(session, chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        async with session.post(BASE_URL, json=payload) as response:
            if response.status != 200:
                print(f"Ошибка {response.status} при отправке пользователю {chat_id}")
            else:
                print(f"Сообщение отправлено пользователю {chat_id}")
    except Exception as e:
        print(f"Ошибка при отправке пользователю {chat_id}: {e}")

async def main():
    session_db = Session()
    try:
        chat_ids = session_db.query(Chat.chat_id).all()
    finally:
        session_db.close()

    chat_ids = [chat_id[0] for chat_id in chat_ids]

    async with aiohttp.ClientSession() as session_http:
        tasks = [send_message(session_http, chat_id, MESSAGE) for chat_id in chat_ids]
        await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())
