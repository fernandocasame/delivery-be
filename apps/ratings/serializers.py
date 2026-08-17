from rest_framework import serializers
from .models import OrderRating

class OrderRatingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderRating
        fields = '__all__'
        read_only_fields = ('rated_by',)
