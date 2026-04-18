"""
Пакет для VK бота
"""
from .bot import VkBot
from .fsm.storage import VkFSMStorage

__all__ = ['VkBot', 'VkFSMStorage']
