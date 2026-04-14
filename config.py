import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID", 0))

GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID")
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
GOOGLE_WORKSHEET_TITLE = os.getenv("GOOGLE_WORKSHEET_TITLE", "Расходы")
BALANCE_CELL = os.getenv("BALANCE_CELL", "G2")

CATEGORIES_FILE = os.getenv("CATEGORIES_FILE", "categories.json")

DEFAULT_EXPENSE_CATEGORIES = [
    "Продукты",
    "Кафе/Рестораны",
    "Транспорт",
    "ЖКХ",
    "Связь и интернет",
    "Развлечения",
    "Одежда",
    "Здоровье",
    "Красота",
    "Подарки",
    "Образование",
    "Прочее"
]

DEFAULT_INCOME_CATEGORIES = [
    "Зарплата",
    "Перевод",
    "Наличные",
    "Прочее"
]
