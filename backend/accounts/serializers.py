from rest_framework import serializers

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """The only shape in which account data leaves the API."""

    class Meta:
        model = User
        fields = ["id", "username", "role"]
        read_only_fields = fields
