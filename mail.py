import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from database.models import Chat
from dotenv import load_dotenv
from telegram import Bot
import asyncio

# Загрузка переменных окружения
load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB-USER')}:{os.getenv('DB-PASSWORD')}@{os.getenv('DB-HOST')}:{os.getenv('DB-PORT')}/{os.getenv('DB-NAME')}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)

# Ваш токен бота
BOT_TOKEN = "7372222308:AAHFLiATAW-MaAKQ4C_0EWEvPvCgLjBk7pw"

# Сообщение, которое нужно отправить
MESSAGE = "pivo."

# Инициализация бота
bot = Bot(token=BOT_TOKEN)

async def send_mail(chat_ids: list):
    for user_id in chat_ids:
        user_id = user_id[0]  # Извлекаем `chat_id` из кортежа
        try:
            await bot.send_message(chat_id=user_id, text=MESSAGE)  # Используем await
            print(f"Сообщение отправлено пользователю {user_id}")
        except Exception as e:
            print(f"Ошибка при отправке пользователю {user_id}: {e}")

async def main():
    session = Session()
    chat_ids = session.query(Chat.chat_id).all()
    session.close()
    print(chat_ids)
    await send_mail(chat_ids=chat_ids)  # Вызываем асинхронную функцию

if __name__ == "__main__":
    asyncio.run(main())  # Запускаем асинхронный код
