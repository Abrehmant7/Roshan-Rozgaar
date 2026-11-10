from django.contrib.auth.models import AbstractUser


class User(AbstractUser):
    """Project user model. Kept minimal; marketplace roles arrive in later phases."""
