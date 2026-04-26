import asyncio
import datetime
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

from aiogram import Bot
from subscriptions_storage import sub_storage
from config import TELEGRAM_USER_ID
from keyboards import get_reminder_keyboard
from google_sheets import gs_client

logger = logging.getLogger(__name__)

async def keep_alive_google_sheets():
    # Простой запрос для обновления токена и поддержания соединения
    try:
        await gs_client.get_balance()
        logger.debug("Keep-alive ping to Google Sheets successful.")
    except Exception as e:
        logger.warning(f"Keep-alive ping to Google Sheets failed: {e}")

async def check_subscriptions(bot: Bot):
    logger.info("Running daily subscription check...")
    tz = pytz.timezone("Europe/Moscow")
    now = datetime.datetime.now(tz)
    
    subs = sub_storage.get_all()
    for s in subs:
        try:
            sub_date = datetime.datetime.strptime(s['date'], "%d.%m.%Y").date()
            if sub_date <= now.date():
                # It's time to pay (or over due)
                text = (
                    f"🔔 <b>Напоминание о платеже!</b>\n\n"
                    f"Подписка/платеж: <b>{s['name']}</b>\n"
                    f"Сумма: <b>{s['amount']}</b>\n"
                    f"Категория: {s['category']}\n\n"
                    f"Записать этот расход в таблицу?"
                )
                await bot.send_message(
                    TELEGRAM_USER_ID, 
                    text, 
                    parse_mode="HTML", 
                    reply_markup=get_reminder_keyboard(s['id'])
                )
        except Exception as e:
            logger.error(f"Error processing subscription {s['name']}: {e}")

def start_scheduler(bot: Bot):
    tz = pytz.timezone("Europe/Moscow")
    scheduler = AsyncIOScheduler(timezone=tz)
    
    # Run daily at 12:00 MSK
    scheduler.add_job(check_subscriptions, 'cron', hour=12, minute=0, args=[bot])
    
    # Run keep-alive ping every 45 minutes
    scheduler.add_job(keep_alive_google_sheets, 'interval', minutes=45)
    
    scheduler.start()
    logger.info("Scheduler started successfully for 12:00 MSK and Keep-Alive (45m)")
