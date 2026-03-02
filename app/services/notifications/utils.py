import asyncio
import functools
import logging
from typing import TypeVar, Callable, Any
from datetime import datetime, timedelta
from collections import defaultdict

import bot.utils.dates as dates

T = TypeVar('T')
logger = logging.getLogger(__name__)


def retry_async(max_retries: int = 3, delay: float = 1, backoff: float = 2):
    """
    Декоратор для повторных попыток асинхронных функций
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        wait_time = delay * (backoff ** attempt)
                        logger.warning(
                            f"Attempt {attempt + 1} failed: {e}. "
                            f"Retrying in {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"All {max_retries} attempts failed")
            raise last_exception

        return wrapper

    return decorator


def rate_limit(max_calls: int, period: float):
    """
    Декоратор для ограничения частоты вызовов
    """
    calls = defaultdict(list)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            now = dates.now()

            # Очищаем старые вызовы
            calls[func.__name__] = [
                call_time for call_time in calls[func.__name__]
                if now - call_time < timedelta(seconds=period)
            ]

            if len(calls[func.__name__]) >= max_calls:
                oldest = calls[func.__name__][0]
                wait_time = (oldest + timedelta(seconds=period) - now).total_seconds()
                if wait_time > 0:
                    logger.warning(f"Rate limit reached, waiting {wait_time}s")
                    await asyncio.sleep(wait_time)

            calls[func.__name__].append(now)
            return await func(*args, **kwargs)

        return wrapper

    return decorator


def chunks(lst: list, n: int):
    """Разбивает список на чанки"""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


async def gather_with_concurrency(n: int, *tasks):
    """Запускает задачи с ограничением по конкурентности"""
    semaphore = asyncio.Semaphore(n)

    async def sem_task(task):
        async with semaphore:
            return await task

    return await asyncio.gather(*(sem_task(task) for task in tasks))
