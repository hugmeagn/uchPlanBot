import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from bot.handlers import router
from bot_integration.integration import setup_integration
from bot.middlewares.services import ServicesMiddleware
from database.connection import init_db, close_db

import config


async def main():
    """Главная функция"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    logging.info("🚀 Запускаем бота...")

    # 1. Подключаем базу данных
    await init_db()
    logging.info("✅ База данных подключена")

    # 2. Создаем бота и диспетчер
    bot = Bot(token=config.BOT_TOKEN, default=config.DEFAULT_BOT_SETTINGS)
    dp = Dispatcher(storage=MemoryStorage())

    # 3. СНАЧАЛА добавляем middleware (до регистрации роутера!)
    dp.message.middleware(ServicesMiddleware())
    dp.callback_query.middleware(ServicesMiddleware())
    logging.info("✅ Middleware подключены")

    # 4. Запускаем сервисы задач и уведомлений
    #    Важно: это нужно сделать ДО подключения роутера,
    #    чтобы сервисы были доступны в хендлерах
    integration = setup_integration(bot, dp)
    await integration.initialize_services()
    logging.info("✅ Сервисы задач и уведомлений запущены")

    # 5. ПОТОМ подключаем обработчики команд
    #    (теперь в них уже доступны сервисы через middleware)
    dp.include_router(router)
    logging.info("✅ Обработчики команд подключены")

    try:
        logging.info("🎯 Бот готов к работе! Начинаем принимать сообщения...")
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"❌ Ошибка при работе бота: {e}")
    finally:
        logging.info("🛑 Останавливаем бота...")

        # 8. Очищаем сервисы
        await integration.cleanup()
        logging.info("✅ Сервисы остановлены")

        # 9. Закрываем соединения с БД
        await close_db()
        logging.info("✅ Соединения с БД закрыты")

        # 10. Закрываем сессию бота
        await bot.session.close()
        logging.info("✅ Сессия бота закрыта")

        logging.info("👋 Бот остановлен. До свидания!")


if __name__ == "__main__":
    asyncio.run(main())
