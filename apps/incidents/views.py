from rest_framework import serializers, generics, permissions
from .models import IncidentTicket

class IncidentTicketSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncidentTicket
        fields = '__all__'
        read_only_fields = ('reported_by', 'status', 'resolution_notes')


class IncidentListCreateView(generics.ListCreateAPIView):
    serializer_class = IncidentTicketSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        if self.request.user.role == 'ADMIN':
            return IncidentTicket.objects.all().order_by('-created_at')
        return IncidentTicket.objects.filter(reported_by=self.request.user).order_by('-created_at')

    def perform_create(self, serializer):
        serializer.save(reported_by=self.request.user)
