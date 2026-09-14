from celery import shared_task
from django.utils import timezone
from .models import ScheduledPost, PostAttempt, Notification
from .instagram_api import InstagramAPIClient


@shared_task
def publish_scheduled_post(post_id):
    try:
        post = ScheduledPost.objects.get(id=post_id)
    except ScheduledPost.DoesNotExist:
        return f"Post #{post_id} not found"

    if post.status == "published":
        return f"Post #{post_id} already published"

    post.status = "processing"
    post.last_attempt_at = timezone.now()
    post.save()

    client = InstagramAPIClient(account=post.account)
    
    # We construct full image URL if available
    image_url = ""
    if post.image:
        image_url = post.image.url

    full_caption = f"{post.caption}\n\n{post.hashtags}".strip() if post.hashtags else post.caption

    success, media_id, message = client.publish_image(image_url, full_caption)

    # Log post attempt
    PostAttempt.objects.create(
        post=post,
        status="success" if success else "failed",
        error_message=message if not success else "",
        response_data=f"media_id: {media_id}" if media_id else message
    )

    if success and media_id:
        post.status = "published"
        post.instagram_media_id = media_id
        post.published_at = timezone.now()
        post.error_message = ""
        post.save()

        Notification.objects.create(
            user=post.user,
            title="Post Published Successfully",
            message=f"Your scheduled post for {post.scheduled_at:%Y-%m-%d %H:%M} was published to Instagram.",
            category="published"
        )
        return f"Post #{post_id} published successfully: {media_id}"
    else:
        post.status = "failed"
        post.retry_count += 1
        post.error_message = message
        post.save()

        Notification.objects.create(
            user=post.user,
            title="Post Publishing Failed",
            message=f"Failed to publish post scheduled for {post.scheduled_at:%Y-%m-%d %H:%M}: {message}",
            category="failed"
        )
        return f"Post #{post_id} publishing failed: {message}"


@shared_task
def process_due_posts():
    due_posts = ScheduledPost.objects.filter(
        status="scheduled",
        scheduled_at__lte=timezone.now()
    )
    count = due_posts.count()
    for post in due_posts:
        publish_scheduled_post.delay(post.id)
    return f"Triggered {count} due posts for publishing"
