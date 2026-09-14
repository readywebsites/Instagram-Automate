import datetime
from datetime import timedelta
import json
import requests

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.conf import settings
from django.utils import timezone

from .forms import (
    ScheduledPostForm,
    ContentItemForm,
    BulkUploadForm,
    ScheduleGeneratorForm,
    UserProfileForm
)
from .models import (
    ScheduledPost,
    InstagramAccount,
    ContentItem,
    Schedule,
    PostAttempt,
    Notification,
    UserProfile
)
from .tasks import publish_scheduled_post


# =========================
# HOME
# =========================

def home(request):
    return render(request, "home.html")


# =========================
# AUTHENTICATION
# =========================

def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect("dashboard")
        else:
            messages.error(request, "Invalid username or password.")

    return render(request, "auth/login.html")


def signup_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        email = request.POST.get("email")
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if not username or not email or not password:
            messages.error(request, "Please fill all required fields.")
            return render(request, "auth/signup.html")

        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, "auth/signup.html")

        if User.objects.filter(username=username).exists():
            messages.error(request, "Username is already taken.")
            return render(request, "auth/signup.html")

        if User.objects.filter(email=email).exists():
            messages.error(request, "Email is already registered.")
            return render(request, "auth/signup.html")

        user = User.objects.create_user(username=username, email=email, password=password)
        login(request, user)

        Notification.objects.create(
            user=user,
            title="Welcome to IG Scheduler!",
            message="Your account has been created successfully. Plan your 1-year Instagram strategy now.",
            category="system"
        )

        messages.success(request, "Account created successfully! Welcome to IG Scheduler.")
        return redirect("dashboard")

    return render(request, "auth/signup.html")


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect("home")


def password_reset_view(request):
    if request.method == "POST":
        form = PasswordResetForm(request.POST)
        if form.is_valid():
            form.save(
                request=request,
                use_https=request.is_secure(),
                email_template_name="auth/password_reset_email.html"
            )
            messages.success(request, "Password reset instructions have been sent to your email if it exists.")
            return redirect("login")
    else:
        form = PasswordResetForm()
    return render(request, "auth/password_reset.html", {"form": form})


# =========================
# DASHBOARD
# =========================

@login_required(login_url="login")
def dashboard(request):
    user_posts = ScheduledPost.objects.filter(user=request.user)
    user_images = ContentItem.objects.filter(user=request.user)
    user_accounts = InstagramAccount.objects.filter(user=request.user)

    now = timezone.now()
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    start_of_year = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)

    connected_account = user_accounts.filter(connected=True).first()
    next_post = user_posts.filter(status="scheduled", scheduled_at__gte=now).order_by("scheduled_at").first()

    notifications = Notification.objects.filter(user=request.user, is_read=False)[:5]

    context = {
        "total_posts": user_posts.count(),
        "scheduled_posts": user_posts.filter(status="scheduled").count(),
        "published_posts": user_posts.filter(status="published").count(),
        "failed_posts": user_posts.filter(status="failed").count(),
        "remaining_posts": user_posts.filter(status__in=["scheduled", "draft"]).count(),
        "total_images": user_images.count(),
        "connected_account": connected_account,
        "next_post": next_post,
        "posts_this_month": user_posts.filter(scheduled_at__gte=start_of_month).count(),
        "posts_this_year": user_posts.filter(scheduled_at__gte=start_of_year).count(),
        "recent_posts": user_posts.order_by("-created_at")[:5],
        "upcoming_posts": user_posts.filter(status="scheduled", scheduled_at__gte=now).order_by("scheduled_at")[:5],
        "notifications": notifications,
    }

    return render(request, "dashboard/dashboard.html", context)


@login_required(login_url="login")
def calendar_view(request):
    return render(request, "dashboard/calendar.html")


@login_required(login_url="login")
def calendar_events_api(request):
    posts = ScheduledPost.objects.filter(user=request.user)
    events = []
    for post in posts:
        color_map = {
            "scheduled": "#3b82f6",
            "published": "#10b981",
            "failed": "#ef4444",
            "draft": "#6b7280",
            "processing": "#f59e0b",
            "cancelled": "#9ca3af",
        }
        events.append({
            "id": post.id,
            "title": post.caption[:30] if post.caption else f"Post #{post.id}",
            "start": post.scheduled_at.isoformat(),
            "backgroundColor": color_map.get(post.status, "#3b82f6"),
            "borderColor": color_map.get(post.status, "#3b82f6"),
            "extendedProps": {
                "status": post.get_status_display(),
                "caption": post.caption,
                "image_url": post.image.url if post.image else "",
                "scheduled_at": post.scheduled_at.strftime("%b %d, %Y %I:%M %p"),
                "error_message": post.error_message,
            }
        })
    return JsonResponse(events, safe=False)


# =========================
# BULK UPLOAD & CONTENT ITEMS
# =========================

@login_required(login_url="login")
def bulk_upload(request):
    if request.method == "POST":
        form = BulkUploadForm(request.POST, request.FILES)
        if form.is_valid():
            files = request.FILES.getlist("images")
            uploaded_count = 0
            for f in files:
                ContentItem.objects.create(
                    user=request.user,
                    image=f,
                    title=f.name,
                    status="draft"
                )
                uploaded_count += 1
            messages.success(request, f"Successfully uploaded {uploaded_count} images to your content library.")
            return redirect("bulk_upload")
    else:
        form = BulkUploadForm()

    user_images = ContentItem.objects.filter(user=request.user)
    return render(request, "posts/upload.html", {"form": form, "images": user_images})


@login_required(login_url="login")
def delete_content_item(request, pk):
    item = get_object_or_404(ContentItem, pk=pk, user=request.user)
    if request.method == "POST":
        item.delete()
        messages.success(request, "Image deleted from content library.")
        return redirect("bulk_upload")
    return redirect("bulk_upload")


# =========================
# 1-YEAR SCHEDULER ENGINE
# =========================

@login_required(login_url="login")
def schedule_create(request):
    if request.method == "POST":
        form = ScheduleGeneratorForm(request.POST, request.FILES)
        if form.is_valid():
            schedule_obj = form.save(commit=False)
            schedule_obj.user = request.user

            if schedule_obj.duration_days == 0:
                schedule_obj.duration_days = form.cleaned_data.get("custom_days") or 365

            schedule_obj.save()

            # Handle direct image upload on schedule form if provided
            uploaded_files = request.FILES.getlist("images")
            for f in uploaded_files:
                ContentItem.objects.create(
                    user=request.user,
                    image=f,
                    title=f.name,
                    caption=schedule_obj.default_description,
                    hashtags=schedule_obj.default_hashtags,
                    status="draft"
                )

            # Schedule Generation Logic
            start_date = schedule_obj.start_date
            posting_time = schedule_obj.posting_time
            duration_days = schedule_obj.duration_days
            frequency = schedule_obj.frequency
            overflow_strategy = schedule_obj.overflow_strategy
            default_desc = schedule_obj.default_description
            default_tags = schedule_obj.default_hashtags

            step = 1
            if frequency == "every_2_days":
                step = 2
            elif frequency == "weekly":
                step = 7

            content_items = list(ContentItem.objects.filter(user=request.user, status="draft"))
            account = InstagramAccount.objects.filter(user=request.user, connected=True).first()

            current_date = start_date
            end_date = start_date + timedelta(days=duration_days)
            item_index = 0
            created_count = 0

            while current_date < end_date:
                naive_dt = datetime.datetime.combine(current_date, posting_time)
                scheduled_at = timezone.make_aware(naive_dt)

                content_item = None
                image_file = None
                caption = default_desc
                hashtags = default_tags

                if content_items:
                    if item_index < len(content_items):
                        content_item = content_items[item_index]
                        image_file = content_item.image
                        caption = content_item.caption if content_item.caption else default_desc
                        hashtags = content_item.hashtags if content_item.hashtags else default_tags
                        content_item.status = "scheduled"
                        content_item.save()
                        item_index += 1
                    elif overflow_strategy == "repeat":
                        content_item = content_items[item_index % len(content_items)]
                        image_file = content_item.image
                        caption = content_item.caption if content_item.caption else default_desc
                        hashtags = content_item.hashtags if content_item.hashtags else default_tags
                        item_index += 1
                    elif overflow_strategy == "stop":
                        break

                if image_file or overflow_strategy == "empty":
                    ScheduledPost.objects.create(
                        user=request.user,
                        schedule=schedule_obj,
                        account=account,
                        content_item=content_item,
                        image=image_file if image_file else "",
                        caption=caption,
                        hashtags=hashtags,
                        scheduled_at=scheduled_at,
                        status="scheduled" if image_file else "draft"
                    )
                    created_count += 1

                current_date += timedelta(days=step)

            messages.success(
                request,
                f"Generated schedule '{schedule_obj.name}' with {created_count} posts over {duration_days} days!"
            )
            return redirect("posts_list")
    else:
        form = ScheduleGeneratorForm(initial={
            "duration_days": 365,
            "start_date": timezone.now().date(),
            "posting_time": "10:00:00",
            "name": f"My {timezone.now().year} Content Plan",
            "default_hashtags": "#fashion #style #newcollection"
        })

    user_images_count = ContentItem.objects.filter(user=request.user, status="draft").count()
    return render(request, "schedule/create.html", {"form": form, "user_images_count": user_images_count})



@login_required(login_url="login")
def schedule_list(request):
    schedules = Schedule.objects.filter(user=request.user)
    return render(request, "schedule/list.html", {"schedules": schedules})


@login_required(login_url="login")
def schedule_toggle_pause(request, pk):
    schedule = get_object_or_404(Schedule, pk=pk, user=request.user)
    if schedule.status == "active":
        schedule.status = "paused"
        messages.info(request, f"Schedule '{schedule.name}' has been paused.")
    else:
        schedule.status = "active"
        messages.success(request, f"Schedule '{schedule.name}' is now active.")
    schedule.save()
    return redirect("schedule_list")


# =========================
# POST MANAGEMENT
# =========================

@login_required(login_url="login")
def posts_list(request):
    queryset = ScheduledPost.objects.filter(user=request.user)

    status_filter = request.GET.get("status")
    search_query = request.GET.get("search")
    sort_by = request.GET.get("sort", "scheduled_at")

    if status_filter:
        queryset = queryset.filter(status=status_filter)

    if search_query:
        queryset = queryset.filter(
            Q(caption__icontains=search_query) |
            Q(hashtags__icontains=search_query)
        )

    if sort_by in ["scheduled_at", "-scheduled_at", "created_at", "-created_at"]:
        queryset = queryset.order_by(sort_by)

    paginator = Paginator(queryset, 15)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    context = {
        "page_obj": page_obj,
        "status_filter": status_filter,
        "search_query": search_query,
        "sort_by": sort_by,
        "total_count": queryset.count(),
    }
    return render(request, "posts/list.html", context)


@login_required(login_url="login")
def post_create(request):
    if request.method == "POST":
        form = ScheduledPostForm(request.POST, request.FILES)
        if form.is_valid():
            post = form.save(commit=False)
            post.user = request.user
            if not post.account:
                post.account = InstagramAccount.objects.filter(user=request.user, connected=True).first()
            post.save()
            messages.success(request, "Post scheduled successfully.")
            return redirect("posts_list")
    else:
        form = ScheduledPostForm()

    user_accounts = InstagramAccount.objects.filter(user=request.user)
    return render(request, "posts/create.html", {"form": form, "user_accounts": user_accounts})


@login_required(login_url="login")
def post_detail(request, pk):
    post = get_object_or_404(ScheduledPost, pk=pk, user=request.user)
    attempts = post.attempts.all()
    return render(request, "posts/detail.html", {"post": post, "attempts": attempts})


@login_required(login_url="login")
def post_edit(request, pk):
    post = get_object_or_404(ScheduledPost, pk=pk, user=request.user)
    if request.method == "POST":
        form = ScheduledPostForm(request.POST, request.FILES, instance=post)
        if form.is_valid():
            form.save()
            messages.success(request, "Post updated successfully.")
            return redirect("post_detail", pk=post.pk)
    else:
        form = ScheduledPostForm(instance=post)

    return render(request, "posts/edit.html", {"form": form, "post": post})


@login_required(login_url="login")
def post_delete(request, pk):
    post = get_object_or_404(ScheduledPost, pk=pk, user=request.user)
    if request.method == "POST":
        post.delete()
        messages.success(request, "Post deleted successfully.")
        return redirect("posts_list")
    return render(request, "posts/delete_confirm.html", {"post": post})


@login_required(login_url="login")
def post_retry(request, pk):
    post = get_object_or_404(ScheduledPost, pk=pk, user=request.user)
    if request.method == "POST":
        post.status = "scheduled"
        post.save()
        publish_scheduled_post.delay(post.id)
        messages.info(request, "Post retry triggered. Publishing task has been queued.")
        return redirect("post_detail", pk=post.pk)
    return redirect("post_detail", pk=post.pk)


# =========================
# INSTAGRAM ACCOUNT MANAGEMENT
# =========================

@login_required(login_url="login")
def instagram_accounts(request):
    accounts = InstagramAccount.objects.filter(user=request.user)
    meta_configured = bool(settings.META_APP_ID and settings.META_APP_SECRET)
    context = {
        "accounts": accounts,
        "meta_configured": meta_configured,
        "meta_app_id": settings.META_APP_ID,
    }
    return render(request, "instagram/accounts.html", context)


@login_required(login_url="login")
def instagram_connect(request):
    if not settings.META_APP_ID or not settings.META_APP_SECRET:
        messages.warning(
            request,
            "Meta API is not configured yet. Add META_APP_ID and META_APP_SECRET in your .env file."
        )
        return redirect("instagram_accounts")

    # Construct Meta OAuth URL
    redirect_uri = settings.META_REDIRECT_URI
    scope = "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement"
    oauth_url = (
        f"https://www.facebook.com/{settings.INSTAGRAM_GRAPH_VERSION}/dialog/oauth"
        f"?client_id={settings.META_APP_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&scope={scope}"
        f"&response_type=code"
    )
    return redirect(oauth_url)


@login_required(login_url="login")
def instagram_callback(request):
    code = request.GET.get("code")
    error = request.GET.get("error")

    if error or not code:
        messages.error(request, f"Meta authorization failed: {error or 'No authorization code returned'}")
        return redirect("instagram_accounts")

    # Exchange code for access token
    token_url = f"https://graph.facebook.com/{settings.INSTAGRAM_GRAPH_VERSION}/oauth/access_token"
    params = {
        "client_id": settings.META_APP_ID,
        "redirect_uri": settings.META_REDIRECT_URI,
        "client_secret": settings.META_APP_SECRET,
        "code": code,
    }

    try:
        resp = requests.get(token_url, params=params, timeout=15)
        data = resp.json()
        if "access_token" in data:
            access_token = data["access_token"]
            # Get user info
            me_url = f"https://graph.facebook.com/{settings.INSTAGRAM_GRAPH_VERSION}/me?fields=id,name&access_token={access_token}"
            me_resp = requests.get(me_url, timeout=15).json()
            ig_id = me_resp.get("id", "")
            name = me_resp.get("name", "Instagram Account")

            account, created = InstagramAccount.objects.get_or_create(
                user=request.user,
                instagram_user_id=ig_id,
                defaults={"username": name, "access_token": access_token, "connected": True}
            )
            if not created:
                account.access_token = access_token
                account.username = name
                account.connected = True
                account.save()

            messages.success(request, f"Successfully connected Instagram account '@{account.username}'!")
        else:
            err_msg = data.get("error", {}).get("message", "Token exchange failed")
            messages.error(request, f"Failed to exchange token: {err_msg}")
    except Exception as e:
        messages.error(request, f"Meta connection error: {str(e)}")

    return redirect("instagram_accounts")


@login_required(login_url="login")
def instagram_disconnect(request, pk):
    account = get_object_or_404(InstagramAccount, pk=pk, user=request.user)
    if request.method == "POST":
        account.connected = False
        account.access_token = ""
        account.save()
        messages.info(request, f"Disconnected Instagram account '{account.username}'.")
    return redirect("instagram_accounts")


# =========================
# USER SETTINGS & NOTIFICATIONS
# =========================

@login_required(login_url="login")
def settings_view(request):
    profile, created = UserProfile.objects.get_or_create(user=request.user)

    if request.method == "POST":
        if "update_profile" in request.POST:
            email = request.POST.get("email")
            username = request.POST.get("username")

            if username and username != request.user.username:
                if User.objects.filter(username=username).exclude(pk=request.user.pk).exists():
                    messages.error(request, "Username is already taken.")
                else:
                    request.user.username = username

            if email and email != request.user.email:
                if User.objects.filter(email=email).exclude(pk=request.user.pk).exists():
                    messages.error(request, "Email is already taken.")
                else:
                    request.user.email = email

            request.user.save()

            form = UserProfileForm(request.POST, instance=profile)
            if form.is_valid():
                form.save()
                messages.success(request, "Settings updated successfully.")
                return redirect("settings")

        elif "change_password" in request.POST:
            pwd_form = SetPasswordForm(request.user, request.POST)
            if pwd_form.is_valid():
                user = pwd_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, "Your password was successfully updated!")
                return redirect("settings")
            else:
                messages.error(request, "Please correct the password errors below.")
    else:
        form = UserProfileForm(instance=profile)
        pwd_form = SetPasswordForm(request.user)

    return render(request, "settings/settings.html", {"form": form, "pwd_form": pwd_form, "profile": profile})


@login_required(login_url="login")
def notification_read(request, pk):
    notif = get_object_or_404(Notification, pk=pk, user=request.user)
    notif.is_read = True
    notif.save()
    return JsonResponse({"status": "success"})


@login_required(login_url="login")
def notification_mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    messages.success(request, "All notifications marked as read.")
    return redirect("dashboard")