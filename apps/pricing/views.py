from rest_framework import generics, permissions, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import VehicleTariff, SpecialSurgeRate
from .serializers import VehicleTariffSerializer, SpecialSurgeRateSerializer, PriceEstimateRequestSerializer
from .services import PricingEngine

class VehicleTariffListView(generics.ListCreateAPIView):
    queryset = VehicleTariff.objects.all()
    serializer_class = VehicleTariffSerializer
    permission_classes = [permissions.AllowAny]


class VehicleTariffDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = VehicleTariff.objects.all()
    serializer_class = VehicleTariffSerializer
    permission_classes = [permissions.IsAdminUser]


class EstimatePriceView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PriceEstimateRequestSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data
            estimate = PricingEngine.calculate_price(
                distance_km=data.get('distance_km', 5.0),
                duration_minutes=data.get('duration_minutes', 15.0),
                vehicle_type=data.get('vehicle_type', 'MOTO'),
                is_night=data.get('is_night', False),
                is_rain=data.get('is_rain', False)
            )
            return Response(estimate)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
