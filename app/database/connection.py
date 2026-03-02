"""
Настройка подключения к базе данных для проекта UchPlan.
"""
import logging
from tortoise import Tortoise, connections
import config

from models import TORTOISE_MODELS

logger = logging.getLogger(__name__)


async def init_db(db_url: str = None):
    """
    Инициализация подключения к базе данных.
    Вызывается при запуске бота.
    """

    db_url = db_url or config.DB_URL

    try:
        await Tortoise.init(
            db_url=db_url,
            modules={'models': TORTOISE_MODELS}
        )

        # Создание таблиц (только для разработки!)
        # В продакшене используйте миграции
        await Tortoise.generate_schemas(safe=True)

        logger.info(f"✅ База данных подключена: {db_url}")

        # Простая проверка подключения
        await connections.get("default").execute_query("SELECT 1")

    except Exception as e:
        logger.error(f"❌ Ошибка подключения к базе данных: {e}")
        raise


async def close_db():
    """
    Закрытие соединений с базой данных.
    Вызывается при остановке бота.
    """
    await connections.close_all()
    logger.info("Соединения с БД закрыты")


# Контекстный менеджер для работы с транзакциями
class DatabaseTransaction:
    """
    Контекстный менеджер для выполнения операций в транзакции.

    Пример использования:
    async with DatabaseTransaction():
        user = await User.create(...)
        await Task.create(user=user, ...)
    """

    def __init__(self, connection_name: str = "default"):
        self.connection_name = connection_name

    async def __aenter__(self):
        self.connection = connections.get(self.connection_name)
        await self.connection.execute_begin()
        return self.connection

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            await self.connection.execute_rollback()
            logger.error(f"Транзакция отменена: {exc_val}")
        else:
            await self.connection.execute_commit()


# Вспомогательные функции для работы с БД
async def get_db_connection():
    """
    Получение активного соединения с БД.

    Returns:
        Объект соединения с базой данных
    """
    return connections.get("default")


async def is_database_connected() -> bool:
    """
    Проверка подключения к базе данных.

    Returns:
        True если подключение активно, иначе False
    """
    try:
        conn = await get_db_connection()
        await conn.execute_query("SELECT 1")
        return True

    except Exception:
        return False


# Функция для тестирования подключения
async def test_connection():
    """Тестирование подключения к БД"""
    try:
        await init_db()
        print("✅ Подключение к БД успешно установлено")
        await close_db()

    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")


if __name__ == "__main__":
    # Тестирование модуля
    import asyncio

    asyncio.run(test_connection())
