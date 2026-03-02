from models.user import User


async def format_user(user: User):
    """
    Форматирует информацию о пользователе для отображения.
    """
    await user.fetch_related('institution')

    institution_name = user.institution.name if user.institution else "Не указано"

    if user.role == "teacher":
        # Для преподавателя показываем ФИО и кафедру
        full_name = user.full_name or "Не указано"
        department = user.group or "Не указана"

        return (
            f"• 👨‍🏫 **Роль:** Преподаватель\n"
            f"• 📇 **ФИО:** {full_name}\n"
            f"• 🏫 **Учебное заведение:** {institution_name}\n"
            f"• 🏛️ **Кафедра/факультет:** {department}\n"
            f"• 🔔 **Уведомления:** {'✅ Включены' if user.notifications_enabled else '❌ Выключены'}\n\n"
        )
    else:
        # Для студента
        return (
            f"• 👤 **Роль:** Студент\n"
            f"• 🏫 **Учебное заведение:** {institution_name}\n"
            f"• 👥 **Группа:** {user.group or 'Не указана'}\n"
            f"• 🔔 **Уведомления:** {'✅ Включены' if user.notifications_enabled else '❌ Выключены'}\n\n"
        )
