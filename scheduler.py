import datetime
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import pytz

from aiogram import Bot
from subscriptions_storage import sub_storage
from config import TELEGRAM_USER_ID
from keyboards import get_reminder_keyboard
import html

logger = logging.getLogger(__name__)

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
                    f"Подписка/платеж: <b>{html.escape(str(s['name']), quote=False)}</b>\n"
                    f"Сумма: <b>{s['amount']}</b>\n"
                    f"Категория: {html.escape(str(s['category']), quote=False)}\n\n"
                    f"Записать этот платеж?"
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
    
    scheduler.start()
    logger.info("Scheduler started successfully for daily subscription checks at 12:00 MSK")
