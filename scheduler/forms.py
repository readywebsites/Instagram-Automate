from django import forms
from django.utils import timezone
from .models import ScheduledPost, ContentItem, Schedule, UserProfile, InstagramAccount
import os

SUPPORTED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def validate_image_file(file):
    ext = os.path.splitext(file.name)[1].lower()
    if ext not in SUPPORTED_IMAGE_EXTENSIONS:
        raise forms.ValidationError(f"Unsupported image format '{ext}'. Allowed formats: JPG, JPEG, PNG, WEBP.")
    if file.size > MAX_FILE_SIZE:
        raise forms.ValidationError("Image file size exceeds maximum limit of 10MB.")


class ScheduledPostForm(forms.ModelForm):
    class Meta:
        model = ScheduledPost
        fields = ["image", "caption", "hashtags", "scheduled_at", "account"]
        widgets = {
            "scheduled_at": forms.DateTimeInput(
                attrs={"type": "datetime-local", "class": "form-control"}
            ),
            "caption": forms.Textarea(attrs={"class": "form-control", "rows": 4, "placeholder": "Write your caption..."}),
            "hashtags": forms.TextInput(attrs={"class": "form-control", "placeholder": "#fashion #style #daily"}),
            "account": forms.Select(attrs={"class": "form-select"}),
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, 'file'):
            validate_image_file(image)
        return image

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data.get("scheduled_at")
        if scheduled_at and scheduled_at < timezone.now():
            raise forms.ValidationError("Scheduled date and time cannot be in the past.")
        return scheduled_at


class ContentItemForm(forms.ModelForm):
    class Meta:
        model = ContentItem
        fields = ["image", "title", "caption", "hashtags"]
        widgets = {
            "title": forms.TextInput(attrs={"class": "form-control", "placeholder": "Image title / reference"}),
            "caption": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Default caption..."}),
            "hashtags": forms.TextInput(attrs={"class": "form-control", "placeholder": "#hashtags"}),
            "image": forms.FileInput(attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}),
        }

    def clean_image(self):
        image = self.cleaned_data.get("image")
        if image and hasattr(image, 'file'):
            validate_image_file(image)
        return image


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"class": "form-control", "accept": "image/jpeg,image/png,image/webp"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_file_clean = super().clean
        if isinstance(data, (list, tuple)):
            result = [single_file_clean(d, initial) for d in data]
        else:
            result = [single_file_clean(data, initial)]
        for f in result:
            if f:
                validate_image_file(f)
        return result


class BulkUploadForm(forms.Form):
    images = MultipleFileField(required=True)


class ScheduleGeneratorForm(forms.ModelForm):
    images = MultipleFileField(required=False)
    custom_days = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=1000,
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "Enter custom number of days"})
    )

    class Meta:
        model = Schedule
        fields = [
            "name",
            "default_description",
            "default_hashtags",
            "start_date",
            "posting_time",
            "frequency",
            "duration_days",
            "timezone",
            "overflow_strategy"
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. 2026 Brand Growth Schedule"}),
            "default_description": forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Default post description / caption..."}),
            "default_hashtags": forms.TextInput(attrs={"class": "form-control", "placeholder": "#fashion #style #newcollection"}),
            "start_date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "posting_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "frequency": forms.Select(attrs={"class": "form-select"}),
            "duration_days": forms.Select(attrs={"class": "form-select", "id": "id_duration_days"}),
            "timezone": forms.Select(attrs={"class": "form-select"}),
            "overflow_strategy": forms.Select(attrs={"class": "form-select"}),
        }


    def clean_start_date(self):
        start_date = self.cleaned_data.get("start_date")
        if start_date and start_date < timezone.now().date():
            raise forms.ValidationError("Start date cannot be in the past.")
        return start_date


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ["timezone", "default_posting_time", "default_frequency", "notify_on_publish", "notify_on_failure"]
        widgets = {
            "timezone": forms.TextInput(attrs={"class": "form-control"}),
            "default_posting_time": forms.TimeInput(attrs={"type": "time", "class": "form-control"}),
            "default_frequency": forms.Select(attrs={"class": "form-select"}, choices=[
                ("daily", "Daily"),
                ("every_2_days", "Every 2 Days"),
                ("weekly", "Weekly"),
            ]),
            "notify_on_publish": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "notify_on_failure": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
