import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import BOT_TOKEN
from google_sheets import gs_client
from handlers import router
from scheduler import start_scheduler

async def main():
    if not BOT_TOKEN:
        logging.error("No BOT_TOKEN provided. Ensure .env is set correctly.")
        return

    # Initialize bot and dispatcher
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    
    # Include main router
    dp.include_router(router)
    
    # Init Google Sheets Client
    await gs_client.init()
    
    # Start the scheduler
    start_scheduler(bot)
    
    try:
        logging.info("Starting bot polling...")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())
