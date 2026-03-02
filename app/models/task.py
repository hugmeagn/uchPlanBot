from tortoise import fields, models


class TaskModel(models.Model):
    id = fields.CharField(max_length=36, pk=True)
    user_id = fields.CharField(max_length=100, index=True)
    title = fields.CharField(max_length=200)
    description = fields.TextField(null=True)
    category = fields.CharField(max_length=50, default="other")
    priority = fields.IntField(default=1)
    status = fields.CharField(max_length=50, default="active")
    deadline = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    completed_at = fields.DatetimeField(null=True)
    reminder_enabled = fields.BooleanField(default=True)
    tags = fields.JSONField(default=list)
    metadata = fields.JSONField(default=dict)
    parent_task_id = fields.CharField(max_length=36, null=True)
    subtasks = fields.JSONField(default=list)
    progress = fields.IntField(default=0)

    class Meta:
        table = "tasks"


class TaskReminderModel(models.Model):
    id = fields.CharField(max_length=36, pk=True)
    task = fields.ForeignKeyField("models.TaskModel", related_name="reminders")
    reminder_type = fields.CharField(max_length=50)
    time_before = fields.IntField(null=True)
    custom_time = fields.DatetimeField(null=True)
    sent = fields.BooleanField(default=False)
    sent_at = fields.DatetimeField(null=True)
    notification_id = fields.CharField(max_length=36, null=True)

    class Meta:
        table = "task_reminders"
