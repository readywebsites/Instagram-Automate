from django.urls import path
from . import views

urlpatterns = [
    # Home
    path("", views.home, name="home"),

    # Authentication
    path("login/", views.login_view, name="login"),
    path("signup/", views.signup_view, name="signup"),
    path("logout/", views.logout_view, name="logout"),
    path("password-reset/", views.password_reset_view, name="password_reset"),

    # Dashboard & Calendar
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/calendar/", views.calendar_view, name="calendar"),
    path("dashboard/calendar/events/", views.calendar_events_api, name="calendar_events_api"),

    # Posts Management
    path("posts/", views.posts_list, name="posts_list"),
    path("posts/upload/", views.bulk_upload, name="bulk_upload"),
    path("posts/upload/delete/<int:pk>/", views.delete_content_item, name="delete_content_item"),
    path("posts/create/", views.post_create, name="post_create"),
    path("posts/<int:pk>/", views.post_detail, name="post_detail"),
    path("posts/<int:pk>/edit/", views.post_edit, name="post_edit"),
    path("posts/<int:pk>/delete/", views.post_delete, name="post_delete"),
    path("posts/<int:pk>/retry/", views.post_retry, name="post_retry"),

    # Schedules
    path("schedule/", views.schedule_list, name="schedule_list"),
    path("schedule/create/", views.schedule_create, name="schedule_create"),
    path("schedule/<int:pk>/pause/", views.schedule_toggle_pause, name="schedule_toggle_pause"),

    # Instagram Accounts
    path("instagram/", views.instagram_accounts, name="instagram_accounts"),
    path("instagram/connect/", views.instagram_connect, name="instagram_connect"),
    path("instagram/callback/", views.instagram_callback, name="instagram_callback"),
    path("instagram/<int:pk>/disconnect/", views.instagram_disconnect, name="instagram_disconnect"),

    # User Settings & Notifications
    path("settings/", views.settings_view, name="settings"),
    path("notifications/<int:pk>/read/", views.notification_read, name="notification_read"),
    path("notifications/read-all/", views.notification_mark_all_read, name="notification_mark_all_read"),
]