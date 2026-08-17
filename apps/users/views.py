from rest_framework import generics, status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.contrib.auth import get_user_model
from .models import DriverProfile
from .serializers import (
    UserSerializer, RegisterSerializer, DriverProfileSerializer,
    DriverStatusUpdateSerializer, DriverApprovalSerializer
)

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]


class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class DriverDocumentUploadView(generics.UpdateAPIView):
    serializer_class = DriverProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        profile, _ = DriverProfile.objects.get_or_create(user=self.request.user)
        return profile


class DriverStatusToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def patch(self, request):
        if not hasattr(request.user, 'driver_profile'):
            return Response({'error': 'El usuario no tiene un perfil de repartidor'}, status=status.HTTP_400_BAD_REQUEST)

        profile = request.user.driver_profile
        if profile.approval_status != DriverProfile.ApprovalStatus.APPROVED:
            return Response({'error': 'El perfil de repartidor no está aprobado por el administrador'}, status=status.HTTP_403_FORBIDDEN)

        serializer = DriverStatusUpdateSerializer(profile, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DriverListView(generics.ListAPIView):
    queryset = DriverProfile.objects.all()
    serializer_class = DriverProfileSerializer
    permission_classes = [permissions.IsAdminUser]


class DriverApprovalView(generics.UpdateAPIView):
    queryset = DriverProfile.objects.all()
    serializer_class = DriverApprovalSerializer
    permission_classes = [permissions.IsAdminUser]
