from dataclasses import dataclass
from environs import Env


#@dataclass
#class DatabaseConfig:
#    database: str         # Название базы данных
#    db_host: str          # URL-адрес базы данных
#    db_user: str          # Username пользователя базы данных
#    db_password: str      # Пароль к базе данных


@dataclass
class TgBot:
    token: str            # Токен для доступа к телеграм-боту
    admin_ids: list[str]  # Список id администраторов бота


@dataclass
class Config:
    tg_bot: TgBot
    #db: DatabaseConfig


# Создаем экземпляр класса Env
env: Env = Env()

# Добавляем в переменные окружения данные, прочитанные из файла .env
env.read_env()




def load_config(path) -> Config:

    env: Env = Env()
    env.read_env(path)

    return Config(
        tg_bot=TgBot(
            token=env('BOT_TOKEN'),
            admin_ids=list(map(str, env.list('ADMIN_USERNAMES')))
        )
    )
