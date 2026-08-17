from rest_framework import generics, permissions
from .models import SystemParameter
from .serializers import SystemParameterSerializer

class SystemParameterListCreateView(generics.ListCreateAPIView):
    queryset = SystemParameter.objects.all()
    serializer_class = SystemParameterSerializer
    permission_classes = [permissions.IsAdminUser]


class SystemParameterDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SystemParameter.objects.all()
    serializer_class = SystemParameterSerializer
    lookup_field = 'key'
    permission_classes = [permissions.IsAdminUser]
