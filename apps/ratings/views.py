from rest_framework import generics, permissions
from .models import OrderRating
from .serializers import OrderRatingSerializer
from apps.users.models import DriverProfile

class CreateRatingView(generics.CreateAPIView):
    queryset = OrderRating.objects.all()
    serializer_class = OrderRatingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        rating = serializer.save(rated_by=self.request.user)
        # Update driver rating average if rated user is a driver
        if hasattr(rating.rated_user, 'driver_profile'):
            profile = rating.rated_user.driver_profile
            ratings = OrderRating.objects.filter(rated_user=rating.rated_user)
            profile.total_ratings = ratings.count()
            avg = sum(r.overall_score for r in ratings) / float(profile.total_ratings)
            profile.rating_avg = round(avg, 2)
            profile.save()
