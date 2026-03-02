import os

import pytz
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DEFAULT_BOT_SETTINGS = DefaultBotProperties(parse_mode='Markdown')
DB_URL = os.getenv("DB_URL", "sqlite://database/db.sqlite3")  # Для разработки SQLite

# Настройки парсеров
REQUEST_TIMEOUT = 10
USER_AGENT = "UchPlanBot/1.0 (+https://t.me/your_bot)"

# Настройки уведомлений
REMINDER_BEFORE_CLASS = 15  # минут
REMINDER_BEFORE_DEADLINE = [5, 60, 60*24, 60*24*2]  # минут

TIMEZONE = os.getenv("TIMEZONE", "Asia/Yekaterinburg")
TIMEZONE_OBJ = pytz.timezone(TIMEZONE)

GIGACHAT_CREDENTIALS = os.getenv("GIGACHAT_CREDENTIALS")  # Авторизационные данные
GIGACHAT_SCOPE = os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS")
GIGACHAT_MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat:latest")

# Настройки планировщика
DAILY_PLAN_TIME = os.getenv("DAILY_PLAN_TIME", "08:00")  # Время отправки плана
