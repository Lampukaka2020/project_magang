from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Category, Ticket, TicketFeedback


class RegistrationForm(UserCreationForm):
    first_name = forms.CharField(label="Nama depan",)
    last_name = forms.CharField(label="Nama belakang",)
    email = forms.EmailField(label="Email")

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username",
                 "first_name",
                 "last_name",
                 "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email ini sudah digunakan.")
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.is_staff = False
        user.is_superuser = False
        if commit:
            user.save()
        return user


class TicketForm(forms.ModelForm):
    class Meta:
        model = Ticket
        fields = ("category", "subject", "description", "attachment", "priority")

    Widgets = {
        "subject": forms.TextInput(attrs={"placeholder": "Ringkasan masalah"}),
        "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Jelaskan masalah Anda secara rinci"}),
    }
class TicketUpdateForm(forms.ModelForm):
    action_note = forms.CharField(
        label="Catatan penanganan",
        widget=forms.Textarea(attrs={"rows": 4}),
    )

    class Meta:
        model = Ticket
        fields = ("status", "priority")


class FeedbackForm(forms.ModelForm):
    class Meta:
        model = TicketFeedback
        fields = ("rating", "comments")
        labels = {
            "rating": "Penilaian layanan",
            "comments": "Komentar",
        }
        widgets = {
            "comments": forms.Textarea(
                attrs={
                    "rows": 4,
                    "placeholder": "Ceritakan pengalaman Anda (opsional)",
                }
            )
        }
