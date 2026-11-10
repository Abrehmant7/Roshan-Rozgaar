from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Project user model.

    `role` is the marketplace role only. Django's `is_staff` / `is_superuser`
    stay independent: a staff member can be a customer or a worker, and
    neither marketplace role grants Admin access.
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        WORKER = "worker", "Worker"

    role = models.CharField(max_length=16, choices=Role.choices, default=Role.CUSTOMER)
