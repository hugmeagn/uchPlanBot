from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator
from tortoise.fields import OnDelete


class User(models.Model):
    id = fields.IntField(pk=True)
    telegram_id = fields.BigIntField(unique=True)
    first_name = fields.CharField(max_length=255)
    last_name = fields.CharField(max_length=255, null=True)
    username = fields.CharField(max_length=255, null=True)

    # Профиль
    role = fields.CharField(max_length=20, null=True)  # student/teacher
    full_name = fields.CharField(max_length=255, null=True)  # ФИО для преподавателей
    institution = fields.ForeignKeyField(
        model_name="models.Institution",
        on_delete=OnDelete.SET_NULL,
        null=True
    )
    group = fields.CharField(max_length=100, null=True)  # Для студентов - группа, для преподавателей - кафедра/факультет

    # Настройки
    notifications_enabled = fields.BooleanField(default=True)
    timezone = fields.CharField(max_length=50, default="Europe/Moscow")

    class Meta:
        table = "users"

    def __str__(self):
        return f"{self.first_name} (ID: {self.telegram_id})"


UserPydantic = pydantic_model_creator(User, name="User")
