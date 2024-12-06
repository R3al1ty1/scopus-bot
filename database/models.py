import os

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.declarative import declarative_base
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = f"postgresql://{os.getenv('DB-USER')}:{os.getenv('DB-PASSWORD')}@{os.getenv('DB-HOST')}:{os.getenv('DB-PORT')}/{os.getenv('DB-NAME')}"
engine = create_engine(DATABASE_URL)
Base = declarative_base()
Base.metadata.create_all(engine)

class Chat(Base):
    __tablename__ = 'user_requests'
    chat_id = Column(Integer, primary_key=True)
    username = Column(String)
    requests = Column(Integer, default=0)
    trial_start = Column(String)
