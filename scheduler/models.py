from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    timezone = models.CharField(max_length=50, default="Asia/Kolkata")
    default_posting_time = models.TimeField(default="10:00:00")
    default_frequency = models.CharField(max_length=20, default="daily")
    notify_on_publish = models.BooleanField(default=True)
    notify_on_failure = models.BooleanField(default=True)

    def __str__(self):
        return f"Profile for {self.user.username}"


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, "profile"):
        instance.profile.save()


class InstagramAccount(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="instagram_accounts")
    username = models.CharField(max_length=150, blank=True)
    instagram_user_id = models.CharField(max_length=100, blank=True)
    access_token = models.TextField(blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)
    connected = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username or f"Instagram Account ({self.id})"


class ContentItem(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("assigned", "Assigned"),
        ("scheduled", "Scheduled"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="content_items")
    image = models.ImageField(upload_to="content_library/")
    title = models.CharField(max_length=255, blank=True)
    caption = models.TextField(blank=True)
    hashtags = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title or f"Image #{self.id}"


class Schedule(models.Model):
    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]
    FREQUENCY_CHOICES = [
        ("daily", "Daily (1 post/day)"),
        ("every_2_days", "Every 2 Days"),
        ("weekly", "Weekly"),
        ("custom", "Custom Frequency"),
    ]
    DURATION_CHOICES = [
        (30, "30 Days"),
        (90, "90 Days"),
        (180, "180 Days"),
        (365, "365 Days (1 Year)"),
    ]
    OVERFLOW_CHOICES = [
        ("stop", "Stop when images finish"),
        ("repeat", "Repeat images"),
        ("empty", "Leave dates empty"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="schedules")
    name = models.CharField(max_length=200, default="1-Year Content Schedule")
    default_description = models.TextField(blank=True)
    default_hashtags = models.TextField(blank=True)
    start_date = models.DateField(default=timezone.now)
    posting_time = models.TimeField(default="10:00:00")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default="daily")
    duration_days = models.IntegerField(default=365)
    timezone = models.CharField(max_length=50, default="Asia/Kolkata")
    overflow_strategy = models.CharField(max_length=20, choices=OVERFLOW_CHOICES, default="stop")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    created_at = models.DateTimeField(auto_now_add=True)


    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.duration_days} days) - {self.user.username}"


class ScheduledPost(models.Model):
    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("scheduled", "Scheduled"),
        ("processing", "Processing"),
        ("published", "Published"),
        ("failed", "Failed"),
        ("cancelled", "Cancelled"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="scheduled_posts")
    schedule = models.ForeignKey(Schedule, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    account = models.ForeignKey(InstagramAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts")
    content_item = models.ForeignKey(ContentItem, on_delete=models.SET_NULL, null=True, blank=True, related_name="scheduled_posts")
    image = models.ImageField(upload_to="instagram/")
    caption = models.TextField(blank=True)
    hashtags = models.TextField(blank=True)
    scheduled_at = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    published_at = models.DateTimeField(null=True, blank=True)
    instagram_media_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    retry_count = models.IntegerField(default=0)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"{self.user.username} - {self.scheduled_at:%Y-%m-%d %H:%M} [{self.status}]"


class PostAttempt(models.Model):
    post = models.ForeignKey(ScheduledPost, on_delete=models.CASCADE, related_name="attempts")
    attempted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20)
    error_message = models.TextField(blank=True)
    response_data = models.TextField(blank=True)

    class Meta:
        ordering = ["-attempted_at"]


class Notification(models.Model):
    CATEGORY_CHOICES = [
        ("published", "Post Published"),
        ("failed", "Post Failed"),
        ("disconnected", "Instagram Disconnected"),
        ("schedule_completed", "Schedule Completed"),
        ("token_expired", "Token Expired"),
        ("retry_required", "Retry Required"),
        ("system", "System Notification"),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default="system")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user.username}: {self.title}"
