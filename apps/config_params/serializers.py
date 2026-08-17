from rest_framework import serializers
from .models import SystemParameter

class SystemParameterSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemParameter
        fields = '__all__'
