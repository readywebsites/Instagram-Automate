from django.contrib import admin
from .models import (
    UserProfile,
    InstagramAccount,
    ContentItem,
    Schedule,
    ScheduledPost,
    PostAttempt,
    Notification
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "timezone", "default_posting_time", "default_frequency")
    search_fields = ("user__username", "user__email")


@admin.register(InstagramAccount)
class InstagramAccountAdmin(admin.ModelAdmin):
    list_display = ("username", "user", "instagram_user_id", "connected", "created_at")
    list_filter = ("connected", "created_at")
    search_fields = ("username", "user__username", "instagram_user_id")


@admin.register(ContentItem)
class ContentItemAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("title", "caption", "hashtags", "user__username")


@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "duration_days", "frequency", "status", "created_at")
    list_filter = ("status", "duration_days", "frequency")
    search_fields = ("name", "user__username")


@admin.register(ScheduledPost)
class ScheduledPostAdmin(admin.ModelAdmin):
    list_display = ("user", "scheduled_at", "status", "account", "retry_count", "created_at")
    list_filter = ("status", "scheduled_at", "created_at")
    search_fields = ("caption", "hashtags", "user__username", "instagram_media_id")


@admin.register(PostAttempt)
class PostAttemptAdmin(admin.ModelAdmin):
    list_display = ("post", "status", "attempted_at", "error_message")
    list_filter = ("status", "attempted_at")
    search_fields = ("post__caption", "error_message")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "title", "category", "is_read", "created_at")
    list_filter = ("category", "is_read", "created_at")
    search_fields = ("title", "message", "user__username")
