import asyncio
from app.database.connection import init_db, close_db
from models.institution import Institution


async def add_magtu():
    await init_db()

    # Проверяем, есть ли уже МГТУ
    existing = await Institution.filter(name__icontains="МГТУ").first()

    if not existing:
        institution = await Institution.create(
            name="МГТУ им. Г.И. Носова",
            website="magtu.ru",
            city="Магнитогорск"
        )
        print(f"✅ Добавлено: {institution.name}")
    else:
        print(f"⚠️ Уже существует: {existing.name}")
        if input('Удалить?') == 'Y':
            await existing.delete()

    # Показываем все заведения
    all_inst = await Institution.all()
    print("\n📋 Все учебные заведения:")
    for inst in all_inst:
        print(f"  • {inst.name} - {inst.website}")

    await close_db()


if __name__ == "__main__":
    asyncio.run(add_magtu())