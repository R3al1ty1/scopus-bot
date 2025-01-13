from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import NoResultFound
from sqlalchemy.orm import sessionmaker
from database.models import Chat
from dotenv import load_dotenv
from datetime import datetime, timedelta
from utils.const import MONTHS_DCT
from tasks.tasks import send_message

import os

load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


def new_user(chat_id, username):
    """Добавление нового пользователя и проверка записи в БД."""
    session = Session()

    chat = session.query(Chat).filter_by(chat_id=chat_id).first()
    if not chat:
        now = datetime.now()
        now_str = now.strftime("%Y-%m-%d %H:%M:%S")
        new_date = now + timedelta(days=7)
        new_date_str = new_date.strftime("%Y-%m-%d %H:%M:%S")
        # Если записи нет, добавляем ее
        new_chat = Chat(chat_id=chat_id, username=username, trial_start=now_str, subscription_end=new_date_str)
        session.add(new_chat)
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            print(f"Ошибка при добавлении записи в базу: {e}")

    session.close()

async def charge_request(chat_id):
    """Списание одного запроса у пользователя."""
    session = Session()
    chat = session.query(Chat).filter_by(chat_id=chat_id).first()

    db_time_end = chat.subscription_end
    date_format = "%Y-%m-%d %H:%M:%S"
    end_time = datetime.strptime(db_time_end, date_format)
    now = datetime.now()
    diff = now - end_time

    if diff.days >= 0:
        
        chat.requests -= 1
        session.commit()
    session.close()


def add_requests_error(chat_id, num):
    """Добавление заданного количества запросов пользователю."""

    session = Session()
    chat = session.query(Chat).filter_by(chat_id=chat_id).first()

    db_time_end = chat.subscription_end
    date_format = "%Y-%m-%d %H:%M:%S"
    end_time = datetime.strptime(db_time_end, date_format)
    now = datetime.now()
    diff = now - end_time

    if diff.days >= 0:
        chat.requests += num
        session.commit()
    session.close()


def add_requests(chat_id, num):
    """Добавление заданного количества запросов пользователю."""

    session = Session()
    chat = session.query(Chat).filter_by(chat_id=chat_id).first()

    if num == 0: # если количество запросов 0, значит покупают подписку
        now = datetime.now()
        new_end_time = now + timedelta(days=30) # подписка на 30 дней

        date_format = "%Y-%m-%d %H:%M:%S"
        end_time_str = new_end_time.strftime(date_format)
        chat.subscription_end = end_time_str
        send_message.apply_async(
            (chat_id, "Ваша подписка истекает через 1 день. Продлите её, чтобы продолжать пользоваться сервисом."),
            eta=datetime.now() + timedelta(days=29)
        )

    else:
        chat.requests += num

    session.commit()
    session.close()


def get_requests(chat_id):
    """Получение текущего количества запросов у пользователя."""
    session = Session()
    chat = session.query(Chat).filter_by(chat_id=chat_id).first()
    num = chat.requests
    session.close()

    return num


def get_subscription_status(chat_id):
    status = 'закончилась'
    date_format = "%Y-%m-%d %H:%M:%S"

    session = Session()
    chat = session.query(Chat).filter_by(chat_id=chat_id).first()

    end_date = chat.subscription_end
    
    end = datetime.strptime(end_date, date_format)
    now = datetime.now()
    diff = end - now

    # Преобразуем разницу в секунды
    if diff.total_seconds() >= 0:  # Проверяем разницу в секундах
        status = 'активна'

    # Преобразуем дату окончания в удобный формат
    sub_end = chat.subscription_end.split(' ')[0]
    sub_end = sub_end.split('-')[::-1]

    sub_end[1] = MONTHS_DCT[sub_end[1]]
    sub_end = ' '.join(sub_end)
    
    return status, sub_end


def enough_requests(chat_id):
    session = Session()
    chat = session.query(Chat).filter_by(chat_id=chat_id).first()

    db_time_end = chat.subscription_end
    date_format = "%Y-%m-%d %H:%M:%S"
    end_time = datetime.strptime(db_time_end, date_format)
    now = datetime.now()
    diff = now - end_time

    if diff.days >= 0:
        if chat.requests == 0:
            return False

        session.close()

        return True
    else:
        return True
