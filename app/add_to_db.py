import asyncio

from models.institution import Institution
from database.connection import init_db, close_db

inst_data = [
    {
        "name": "🏛️ Магнитогорский политехнический колледж",
        "city": "Магнитогорск",
        "website": "magpk.ru",
    },
    {
        "name": "🎓 МАГТУ им. Г.И. Носова",
        "city": "Магнитогорск",
        "website": "magtu.ru",
    },
]


async def main():
    await init_db()

    for data in inst_data:
        inst, created = await Institution.get_or_create(
            defaults=data
        )
        if created:
            print(f"✅ Создано заведение: {data['name']}")
        else:
            print(f"ℹ️ Заведение уже существует: {data['name']}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(main())
