from django.contrib import admin
from .models import OrderRating

@admin.register(OrderRating)
class OrderRatingAdmin(admin.ModelAdmin):
    list_display = ('order', 'rated_by', 'rated_user', 'overall_score', 'created_at')
    list_filter = ('overall_score',)
