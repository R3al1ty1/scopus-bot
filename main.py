import logging
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.bot import DefaultBotProperties
from config.config import Config, load_config
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import service_handlers, flow_handlers
from dialogs import dialogs
from aiogram_dialog import setup_dialogs

logging.basicConfig(level=logging.INFO)

async def main() -> None:
    config: Config = load_config(".env")
    storage = MemoryStorage()
    async with Bot(token=config.tg_bot.token, default=DefaultBotProperties(parse_mode=ParseMode.HTML)) as bot:
        dp = Dispatcher(storage=storage)
        # Регистрируем роутеры
        dp.include_router(service_handlers.router)
        dp.include_router(flow_handlers.router)
        dp.include_router(dialogs.main_menu)

        # Настраиваем диалоги
        setup_dialogs(dp)

        # Пропускаем накопившиеся апдейты и запускаем polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
