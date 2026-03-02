from tortoise import fields, models


class NotificationModel(models.Model):
    id = fields.CharField(max_length=36, pk=True)
    user_id = fields.CharField(max_length=100)
    channel = fields.CharField(max_length=50)
    type = fields.CharField(max_length=50)
    priority = fields.IntField()
    status = fields.CharField(max_length=50)
    title = fields.TextField()
    content = fields.TextField()
    data = fields.JSONField(null=True)
    scheduled_for = fields.DatetimeField(null=True)
    sent_at = fields.DatetimeField(null=True)
    delivered_at = fields.DatetimeField(null=True)
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)
    retry_count = fields.IntField(default=0)
    max_retries = fields.IntField(default=3)
    last_error = fields.TextField(null=True)
    metadata = fields.JSONField(default=dict)

    class Meta:
        table = "notifications"


class NotificationTemplateModel(models.Model):
    id = fields.CharField(max_length=36, pk=True)
    name = fields.CharField(max_length=100, unique=True)
    type = fields.CharField(max_length=50)
    channel = fields.CharField(max_length=50)
    title_template = fields.TextField()
    content_template = fields.TextField()
    variables = fields.JSONField(default=list)
    created_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = "notification_templates"
