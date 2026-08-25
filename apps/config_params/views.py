from rest_framework import generics, permissions, status
from rest_framework.response import Response
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

    def update(self, request, *args, **kwargs):
        key = self.kwargs.get('key')
        value = request.data.get('value')
        
        if value is None:
            return Response({'error': 'Valor requerido'}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create parameter to make backend self-healing and avoid 404s
        obj, created = SystemParameter.objects.get_or_create(
            key=key,
            defaults={'value': str(value)}
        )
        if not created:
            obj.value = str(value)
            obj.save()

        serializer = self.get_serializer(obj)
        return Response(serializer.data, status=status.HTTP_200_OK)
