from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.users.models import DriverProfile, VehicleType
from apps.pricing.services import PricingEngine
from apps.orders.models import Order, OrderStatus
from apps.logistics.models import DriverLocation
from apps.logistics.matching_engine import SmartMatchingEngine

User = get_user_model()

class DeliveryPlatformTestCase(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user(
            email='cliente@test.com',
            password='password123',
            first_name='Juan',
            last_name='Perez',
            role=User.Role.CLIENT
        )
        self.driver_user = User.objects.create_user(
            email='repartidor@test.com',
            password='password123',
            first_name='Carlos',
            last_name='Mendoza',
            role=User.Role.DRIVER
        )
        self.driver_profile = DriverProfile.objects.create(
            user=self.driver_user,
            approval_status=DriverProfile.ApprovalStatus.APPROVED,
            status=DriverProfile.Status.AVAILABLE,
            vehicle_type=VehicleType.MOTO
        )
        DriverLocation.objects.create(
            driver=self.driver_user,
            latitude=4.6097,
            longitude=-74.0817
        )

    def test_pricing_engine_calculation(self):
        estimate = PricingEngine.calculate_price(
            distance_km=5.0,
            duration_minutes=15.0,
            vehicle_type='MOTO'
        )
        self.assertEqual(estimate['base_price'], 5000.0)
        self.assertGreater(estimate['total_cost'], 5000.0)
        self.assertIn('platform_fee', estimate)
        self.assertIn('driver_earnings', estimate)

    def test_order_creation_and_matching(self):
        order = Order.objects.create(
            client=self.client_user,
            origin_address='Calle 100 #15-20',
            origin_latitude=4.6095,
            origin_longitude=-74.0815,
            destination_address='Carrera 7 #72-10',
            destination_latitude=4.6150,
            destination_longitude=-74.0750,
            recipient_name='María López',
            recipient_phone='+57 300 123 4567',
            vehicle_type=VehicleType.MOTO,
            status=OrderStatus.SEARCHING,
            total_cost=18500.00
        )
        self.assertEqual(order.status, OrderStatus.SEARCHING)

        eligible_drivers = SmartMatchingEngine.get_nearby_eligible_drivers(order)
        self.assertEqual(len(eligible_drivers), 1)
        self.assertEqual(eligible_drivers[0]['driver'], self.driver_user)

    def test_atomic_order_acceptance(self):
        order = Order.objects.create(
            client=self.client_user,
            origin_address='Calle 100 #15-20',
            origin_latitude=4.6095,
            origin_longitude=-74.0815,
            destination_address='Carrera 7 #72-10',
            destination_latitude=4.6150,
            destination_longitude=-74.0750,
            recipient_name='María López',
            recipient_phone='+57 300 123 4567',
            vehicle_type=VehicleType.MOTO,
            status=OrderStatus.SEARCHING,
            total_cost=18500.00
        )

        result = SmartMatchingEngine.accept_order(order.id, self.driver_user)
        self.assertTrue(result['success'])

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.ACCEPTED)
        self.assertEqual(order.driver, self.driver_user)
