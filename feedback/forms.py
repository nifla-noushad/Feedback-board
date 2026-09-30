from django import forms
from django.contrib.auth.forms import AuthenticationForm

from .models import Feedback
from .validators import validate_image


class FeedbackForm(forms.ModelForm):
    image = forms.ImageField(
        required=False,
        validators=[validate_image],
        error_messages={"invalid_image": "That file isn't a valid image. Use a JPG, PNG or WEBP."},
    )

    class Meta:
        model = Feedback
        fields = ["name", "message", "image"]
        error_messages = {
            "name": {"required": "Enter your name."},
            "message": {
                "required": "Write your feedback.",
            },
        }

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        if not name:
            raise forms.ValidationError("Enter your name.")
        if not all(c.isalpha() or c.isspace() for c in name):
            raise forms.ValidationError("Name can only contain letters and spaces (no numbers or symbols).")
        return name

    def clean_message(self):
        message = self.cleaned_data["message"].strip()
        if not message:
            raise forms.ValidationError("Write your feedback.")
        return message


class AdminFeedbackForm(FeedbackForm):
    """Same as the public form, plus the status field for admins."""

    class Meta(FeedbackForm.Meta):
        fields = ["name", "message", "status", "image"]


class AdminAuthenticationForm(AuthenticationForm):
    """Only staff accounts may log in through the admin login page."""

    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "That username and password don't match. Check them and try again.",
        "not_staff": "This account doesn't have admin access.",
    }

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if not user.is_staff:
            raise forms.ValidationError(self.error_messages["not_staff"], code="not_staff")
