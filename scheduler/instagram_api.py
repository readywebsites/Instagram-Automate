import requests
from django.conf import settings
from django.utils import timezone


class InstagramAPIClient:
    """
    Official Meta Graph API Client for Instagram Content Publishing.
    Follows Meta's 2-step Container creation + Container publishing flow:
    1. POST /{ig-user-id}/media -> returns creation_id (container ID)
    2. POST /{ig-user-id}/media_publish -> publishes container and returns media_id
    """

    def __init__(self, account=None):
        self.account = account
        self.version = getattr(settings, "INSTAGRAM_GRAPH_VERSION", "v23.0")
        self.base_url = f"https://graph.facebook.com/{self.version}"

    def is_configured(self):
        if not getattr(settings, "META_APP_ID", "") or not getattr(settings, "META_APP_SECRET", ""):
            return False, "Meta App ID and Secret are not configured in settings/.env."
        if not self.account or not self.account.connected or not self.account.access_token or not self.account.instagram_user_id:
            return False, "Instagram account is not connected or missing valid access token / user ID."
        return True, "API Configured"

    def publish_image(self, image_url, caption):
        configured, msg = self.is_configured()
        if not configured:
            return False, None, msg

        # Step 1: Create Container
        container_url = f"{self.base_url}/{self.account.instagram_user_id}/media"
        payload = {
            "image_url": image_url,
            "caption": caption,
            "access_token": self.account.access_token
        }
        try:
            resp = requests.post(container_url, data=payload, timeout=30)
            data = resp.json()
            if resp.status_code != 200 or "id" not in data:
                err = data.get("error", {}).get("message", resp.text)
                return False, None, f"Meta Container Creation Error: {err}"
            
            creation_id = data["id"]

            # Step 2: Publish Container
            publish_url = f"{self.base_url}/{self.account.instagram_user_id}/media_publish"
            pub_payload = {
                "creation_id": creation_id,
                "access_token": self.account.access_token
            }
            pub_resp = requests.post(publish_url, data=pub_payload, timeout=30)
            pub_data = pub_resp.json()
            if pub_resp.status_code != 200 or "id" not in pub_data:
                pub_err = pub_data.get("error", {}).get("message", pub_resp.text)
                return False, None, f"Meta Media Publish Error: {pub_err}"

            return True, pub_data["id"], "Successfully published to Instagram"

        except Exception as e:
            return False, None, f"Instagram API Network Error: {str(e)}"
