from django.db import models
from django.core.cache import cache

class SystemParameter(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.set(f"sys_param:{self.key}", self.value, timeout=86400)

    def __str__(self):
        return f"{self.key} = {self.value}"

    @classmethod
    def get_param(cls, key, default=None):
        cached_val = cache.get(f"sys_param:{key}")
        if cached_val is not None:
            return cached_val
        try:
            param = cls.objects.get(key=key)
            cache.set(f"sys_param:{key}", param.value, timeout=86400)
            return param.value
        except cls.DoesNotExist:
            return default
