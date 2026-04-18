"""
Точка входа для VK бота
"""
import asyncio
import logging
import sys
from pathlib import Path

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent))

from app.database.connection import init_db, close_db
from app.vk_bot import VkBot


async def main():
    """Главная функция"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logger = logging.getLogger(__name__)
    logger.info("🚀 Запускаем VK бота...")

    # Подключаем базу данных
    await init_db()
    logger.info("✅ База данных подключена")

    # Создаем и запускаем бота
    bot = VkBot()

    try:
        await bot.start()
    except KeyboardInterrupt:
        logger.info("🛑 Получен сигнал остановки...")
    except Exception as e:
        logger.error(f"❌ Ошибка при работе бота: {e}", exc_info=True)
    finally:
        logger.info("🛑 Останавливаем бота...")
        await bot.stop()
        await close_db()
        logger.info("✅ Соединения с БД закрыты")
        logger.info("👋 VK бот остановлен.")


if __name__ == "__main__":
    asyncio.run(main())
