from tortoise import fields, models
from datetime import datetime
from typing import Optional


class DailyPlan(models.Model):
    """
    Модель для хранения ежедневных планов, сгенерированных GigaChat
    """
    id = fields.IntField(pk=True)
    user = fields.ForeignKeyField("models.User", related_name="daily_plans")

    # Дата, на которую составлен план
    plan_date = fields.DateField()

    # Содержимое плана (текст от GigaChat)
    content = fields.TextField()

    # Метаданные о генерации
    generated_at = fields.DatetimeField(auto_now_add=True)

    # Статус: отправлено ли уведомление пользователю
    notification_sent = fields.BooleanField(default=False)
    sent_at = fields.DatetimeField(null=True)

    # Оценка пользователем (опционально)
    rating = fields.IntField(null=True, min_value=1, max_value=5)
    feedback = fields.TextField(null=True)

    class Meta:
        table = "daily_plans"
        unique_together = (("user", "plan_date"),)  # Один план на пользователя в день

    def __str__(self):
        return f"Plan for {self.user_id} on {self.plan_date}"
