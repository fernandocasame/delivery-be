from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import DriverLocation
from .serializers import DriverLocationSerializer
from .matching_engine import SmartMatchingEngine

class ActiveFleetMapListView(generics.ListAPIView):
    queryset = DriverLocation.objects.all()
    serializer_class = DriverLocationSerializer
    permission_classes = [permissions.IsAuthenticated]


class UpdateLocationRESTView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        lat = request.data.get('latitude')
        lng = request.data.get('longitude')
        heading = request.data.get('heading', 0.0)
        speed = request.data.get('speed', 0.0)

        if lat is None or lng is None:
            return Response({'error': 'Latitud y longitud requeridas'}, status=status.HTTP_400_BAD_REQUEST)

        loc, _ = DriverLocation.objects.get_or_create(
            driver=request.user,
            defaults={'latitude': lat, 'longitude': lng}
        )
        loc.latitude = lat
        loc.longitude = lng
        loc.heading = heading
        loc.speed = speed
        loc.save()

        return Response(DriverLocationSerializer(loc).data)


class DriverAcceptOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, order_id):
        result = SmartMatchingEngine.accept_order(order_id, request.user)
        if result['success']:
            return Response(result, status=status.HTTP_200_OK)
        return Response(result, status=status.HTTP_409_CONFLICT)
