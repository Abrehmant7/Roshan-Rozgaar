from django import forms
from django.contrib.auth import password_validation
from django.core.exceptions import ValidationError

from .models import User


class RegistrationForm(forms.Form):
    username = forms.CharField(
        max_length=User._meta.get_field("username").max_length,
        validators=[User.username_validator],
    )
    password = forms.CharField(strip=False)

    def clean_username(self):
        username = User.normalize_username(self.cleaned_data["username"])
        # Same case-insensitive rule as Django's own UserCreationForm.
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.", code="unique")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            candidate = User(username=cleaned.get("username", ""), role=User.Role.CUSTOMER)
            try:
                password_validation.validate_password(password, candidate)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(strip=False)
