import os
from datetime import datetime, timedelta
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from database.models import Chat, Base
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)
Session = sessionmaker(bind=engine)
session = Session()

inspector = inspect(engine)
if 'user_requests' not in inspector.get_table_names():
    print("Таблица 'user_requests' не найдена в базе данных.")
else:
    try:
        columns = [col['name'] for col in inspector.get_columns('user_requests')]
        if 'subscription_end' not in columns:
            with engine.connect() as connection:
                connection.execute(
                    "ALTER TABLE user_requests ADD COLUMN subscription_end TIMESTAMP"
                )
                print("Поле 'subscription_end' успешно добавлено.")
    except Exception as e:
        print(f"Ошибка при добавлении поля 'subscription_end': {e}")


try:
    users = session.query(Chat).all()
    for user in users:
        if user.trial_start:
            try:
                trial_start_date = datetime.strptime(user.trial_start, "%Y-%m-%d %H:%M:%S")
                user.subscription_end = (trial_start_date + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                print(f"Updated user {user.chat_id}: subscription_end={user.subscription_end}")
            except ValueError as e:
                print(f"Ошибка преобразования trial_start для chat_id={user.chat_id}: {e}")
    session.commit()
    print("Обновление subscription_end завершено успешно.")

except Exception as e:
    print(f"Ошибка при обновлении subscription_end: {e}")
    session.rollback()
