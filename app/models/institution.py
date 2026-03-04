from tortoise import fields, models
from tortoise.contrib.pydantic import pydantic_model_creator


class Institution(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=255)
    website = fields.CharField(max_length=255, null=True)
    city = fields.CharField(max_length=100, null=True)

    def __str__(self):
        return self.name

    class Meta:
        table = "institutions"

