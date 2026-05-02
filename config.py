import os

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv():
        return False

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
TELEGRAM_USER_ID = int(os.getenv("TELEGRAM_USER_ID", 0))

CATEGORIES_FILE = os.getenv("CATEGORIES_FILE", "categories.json")
DATABASE_FILE = os.getenv("DATABASE_FILE", "finance.db")

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
