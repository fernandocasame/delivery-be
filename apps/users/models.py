from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils.translation import gettext_lazy as _

class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError(_('El correo electrónico es obligatorio'))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser debe tener is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser debe tener is_superuser=True.'))

        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    class Role(models.TextChoices):
        CLIENT = 'CLIENT', _('Cliente')
        DRIVER = 'DRIVER', _('Repartidor')
        ADMIN = 'ADMIN', _('Administrador')

    username = None
    email = models.EmailField(_('Correo electrónico'), unique=True)
    phone_number = models.CharField(_('Teléfono'), max_length=20, unique=True, null=True, blank=True)
    role = models.CharField(_('Rol'), max_length=20, choices=Role.choices, default=Role.CLIENT)
    is_phone_verified = models.BooleanField(_('Teléfono verificado'), default=False)
    is_email_verified = models.BooleanField(_('Correo verificado'), default=False)
    profile_photo = models.ImageField(upload_to='profiles/', null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.get_full_name()} ({self.email}) - {self.role}"


class VehicleType(models.TextChoices):
    MOTO = 'MOTO', _('Motocicleta')
    CAR = 'CAR', _('Automóvil')
    VAN = 'VAN', _('Camioneta')
    TRUCK = 'TRUCK', _('Camión')


class DriverProfile(models.Model):
    class ApprovalStatus(models.TextChoices):
        PENDING = 'PENDING', _('Pendiente de aprobación')
        APPROVED = 'APPROVED', _('Aprobado')
        REJECTED = 'REJECTED', _('Rechazado')

    class Status(models.TextChoices):
        OFFLINE = 'OFFLINE', _('Offline')
        AVAILABLE = 'AVAILABLE', _('Disponible')
        BUSY = 'BUSY', _('Ocupado')
        ON_BREAK = 'ON_BREAK', _('En descanso')

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='driver_profile')
    approval_status = models.CharField(max_length=20, choices=ApprovalStatus.choices, default=ApprovalStatus.PENDING)
    rejection_reason = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OFFLINE)
    vehicle_type = models.CharField(max_length=20, choices=VehicleType.choices, default=VehicleType.MOTO)
    vehicle_plate = models.CharField(max_length=15, blank=True, null=True)
    vehicle_brand_model = models.CharField(max_length=100, blank=True, null=True)

    # Documents
    national_id_doc = models.FileField(upload_to='documents/ids/', null=True, blank=True)
    driver_license_doc = models.FileField(upload_to='documents/licenses/', null=True, blank=True)
    personal_photo = models.ImageField(upload_to='documents/photos/', null=True, blank=True)
    vehicle_photo = models.ImageField(upload_to='documents/vehicles/', null=True, blank=True)
    soat_insurance_doc = models.FileField(upload_to='documents/soat/', null=True, blank=True)
    vehicle_registration_doc = models.FileField(upload_to='documents/registration/', null=True, blank=True)
    background_check_doc = models.FileField(upload_to='documents/background/', null=True, blank=True)

    rating_avg = models.FloatField(default=5.0)
    total_ratings = models.IntegerField(default=0)
    acceptance_rate = models.FloatField(default=100.0) # Percentage
    completed_orders_count = models.IntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Repartidor: {self.user.get_full_name()} [{self.approval_status}]"
