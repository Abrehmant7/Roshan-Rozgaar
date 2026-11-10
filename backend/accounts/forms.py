from django import forms
from django.contrib.auth import password_validation
from django.contrib.auth.forms import UsernameField
from django.core.exceptions import ValidationError

from .models import User


class RegistrationForm(forms.Form):
    # UsernameField applies NFKC normalization in to_python(), i.e. BEFORE the
    # max_length and character validators run, so "ﬁ" x 76 (152 chars once
    # normalized) is rejected instead of overflowing the database column.
    username = UsernameField(
        max_length=User._meta.get_field("username").max_length,
        validators=[User.username_validator],
    )
    password = forms.CharField(strip=False)

    def __init__(self, *args, role=User.Role.CUSTOMER, **kwargs):
        super().__init__(*args, **kwargs)
        self.role = role

    def clean_username(self):
        username = User.normalize_username(self.cleaned_data["username"])
        # Case-insensitive, like Django's UserCreationForm; PostgreSQL enforces the
        # same rule (accounts_user_username_ci_unique) for concurrent signups.
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("A user with that username already exists.", code="unique")
        return username

    def clean(self):
        cleaned = super().clean()
        password = cleaned.get("password")
        if password:
            candidate = User(username=cleaned.get("username", ""), role=self.role)
            try:
                password_validation.validate_password(password, candidate)
            except ValidationError as exc:
                self.add_error("password", exc)
        return cleaned


class LoginForm(forms.Form):
    username = forms.CharField()
    password = forms.CharField(strip=False)
