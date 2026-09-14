import datetime
from datetime import timedelta
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile

from scheduler.models import (
    InstagramAccount,
    ContentItem,
    Schedule,
    ScheduledPost,
    PostAttempt,
    Notification
)


class AuthenticationAndIsolationTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user1 = User.objects.create_user(username="user1", email="user1@example.com", password="Password123!")
        self.user2 = User.objects.create_user(username="user2", email="user2@example.com", password="Password123!")

        # Create content for user 1
        self.post_user1 = ScheduledPost.objects.create(
            user=self.user1,
            caption="User 1 post caption",
            scheduled_at=timezone.now() + timedelta(days=1),
            status="scheduled"
        )
        # Create content for user 2
        self.post_user2 = ScheduledPost.objects.create(
            user=self.user2,
            caption="User 2 post caption",
            scheduled_at=timezone.now() + timedelta(days=1),
            status="scheduled"
        )

    def test_signup(self):
        response = self.client.post(reverse("signup"), {
            "username": "newuser",
            "email": "newuser@example.com",
            "password": "Password123!",
            "confirm_password": "Password123!"
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username="newuser").exists())

    def test_login_logout(self):
        login_res = self.client.post(reverse("login"), {
            "username": "user1",
            "password": "Password123!"
        })
        self.assertEqual(login_res.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)

        logout_res = self.client.get(reverse("logout"))
        self.assertEqual(logout_res.status_code, 302)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_protected_dashboard_redirects_unauthenticated(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("login", response.url)

    def test_user_data_isolation(self):
        self.client.force_login(self.user1)

        # Dashboard check
        dashboard_res = self.client.get(reverse("dashboard"))
        self.assertEqual(dashboard_res.status_code, 200)
        self.assertEqual(dashboard_res.context["total_posts"], 1)

        # Posts list check
        posts_res = self.client.get(reverse("posts_list"))
        self.assertEqual(posts_res.status_code, 200)
        posts = posts_res.context["page_obj"]
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0].caption, "User 1 post caption")

        # Try accessing User 2's post detail directly -> should return 404 (or forbidden)
        detail_res = self.client.get(reverse("post_detail", kwargs={"pk": self.post_user2.id}))
        self.assertEqual(detail_res.status_code, 404)


class ScheduleEngine365DayTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="scheduler_user", email="sch@example.com", password="Password123!")
        self.client = Client()
        self.client.force_login(self.user)

    def test_365_day_schedule_generation(self):
        # Upload 5 test content items
        small_gif = (
            b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff'
            b'\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00'
            b'\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b'
        )
        for i in range(5):
            test_file = SimpleUploadedFile(f"test_{i}.png", small_gif, content_type="image/png")
            ContentItem.objects.create(user=self.user, image=test_file, caption=f"Caption {i}", status="draft")

        response = self.client.post(reverse("schedule_create"), {
            "name": "Full 1-Year Campaign",
            "start_date": (timezone.now() + timedelta(days=1)).strftime("%Y-%m-%d"),
            "posting_time": "10:00:00",
            "frequency": "daily",
            "duration_days": 365,
            "timezone": "Asia/Kolkata",
            "overflow_strategy": "repeat"
        })
        self.assertEqual(response.status_code, 302)

        # Check total created scheduled posts
        user_posts = ScheduledPost.objects.filter(user=self.user)
        self.assertEqual(user_posts.count(), 365)

    def test_past_date_validation(self):
        past_date = (timezone.now() - timedelta(days=5)).strftime("%Y-%m-%d")
        response = self.client.post(reverse("schedule_create"), {
            "name": "Past Campaign",
            "start_date": past_date,
            "posting_time": "10:00:00",
            "frequency": "daily",
            "duration_days": 30,
            "timezone": "Asia/Kolkata",
            "overflow_strategy": "stop"
        })
        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "start_date", "Start date cannot be in the past.")


class StatusAndRetryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="retryuser", email="retry@example.com", password="Password123!")

    def test_post_status_initial_state(self):
        post = ScheduledPost.objects.create(
            user=self.user,
            caption="Status test post",
            scheduled_at=timezone.now() + timedelta(days=2),
            status="scheduled"
        )
        self.assertEqual(post.status, "scheduled")
        self.assertEqual(post.retry_count, 0)
        self.assertEqual(post.instagram_media_id, "")
