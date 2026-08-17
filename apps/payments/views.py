from rest_framework import generics, permissions
from .models import DriverWallet
from .serializers import DriverWalletSerializer

class DriverWalletDetailView(generics.RetrieveAPIView):
    serializer_class = DriverWalletSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        wallet, _ = DriverWallet.objects.get_or_create(driver=self.request.user)
        return wallet
