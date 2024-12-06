import os

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Base.metadata.create_all(engine)

class Chat(Base):
    __tablename__ = 'user_requests'
    chat_id = Column(Integer, primary_key=True)
    username = Column(String)
    requests = Column(Integer, default=0)
    trial_start = Column(String)
