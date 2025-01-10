import os
import logging
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Chat
from dotenv import load_dotenv

load_dotenv()

BOT_ADMIN = os.getenv('BOT_ADMIN')
BOT_TOKEN = os.getenv('BOT_TOKEN')
DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)

ALLOWED_USERNAMES = os.getenv('ALLOWED_USERNAMES', '').split(',')

bot1 = Bot(token=BOT_ADMIN)
bot2 = Bot(token=BOT_TOKEN)
dp = Dispatcher()

logging.basicConfig(level=logging.INFO)

class SendMessageStates(StatesGroup):
    waiting_for_message = State()

def get_all_chat_ids():
    session_db = Session()
    try:
        chat_ids = session_db.query(Chat.chat_id).all()
    finally:
        session_db.close()
    
    return [chat_id[0] for chat_id in chat_ids]

async def send_message_to_all_users(message_text: str):
    chat_ids = get_all_chat_ids()
    for chat_id in chat_ids:
        try:
            await bot2.send_message(chat_id, message_text)
            logging.info(f"Сообщение отправлено пользователю {chat_id}")
        except Exception as e:
            logging.error(f"Ошибка при отправке пользователю {chat_id}: {e}")
            await asyncio.sleep(1)

@dp.message(Command('send'))
async def send_command(message: types.Message, state: FSMContext):
    user = message.from_user
    if user.username and user.username.lower() in ALLOWED_USERNAMES:
        await state.set_state(SendMessageStates.waiting_for_message)
        await message.reply("Введите сообщение, которое вы хотите отправить всем пользователям:")
    else:
        await message.reply("У вас нет доступа к этой команде.")

@dp.message(SendMessageStates.waiting_for_message)
async def process_message(message: types.Message, state: FSMContext):
    user_message = message.text
    await send_message_to_all_users(user_message)
    await message.reply("Сообщение отправлено всем пользователям!")
    await state.clear()

async def on_shutdown(dispatcher: Dispatcher):
    await dispatcher.storage.close()
    await dispatcher.storage.wait_closed()
    await bot1.session.close()
    await bot2.session.close()

if __name__ == '__main__':
    try:
        dp.run_polling(bot1, skip_updates=True, on_shutdown=on_shutdown)
    except (KeyboardInterrupt, SystemExit):
        logging.info("Бот остановлен.")