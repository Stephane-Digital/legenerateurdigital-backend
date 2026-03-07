import requests
import base64


def publish_tiktok(post, account):
    """
    TikTok API here is a simplified placeholder.
    Supports:
      - post.image_base64 OR post.image_url (downloaded)
      - post.content
    """

    if not getattr(post, "image_base64", None) and getattr(post, "image_url", None):
        dl = requests.get(post.image_url, timeout=30)
        if dl.status_code != 200:
            raise Exception(f"TikTok download failed: {dl.text}")
        post.image_base64 = base64.b64encode(dl.content).decode("utf-8")

    if not getattr(post, "image_base64", None):
        raise Exception("TikTok requires an image or video")

    access_token = account.access_token

    # TikTok nécessite un upload préalable
    upload_url = "https://open.tiktokapis.com/v2/post/publish/content/upload/"

    image_bytes = base64.b64decode(post.image_base64)

    up = requests.post(
        upload_url,
        headers={"Authorization": f"Bearer {access_token}"},
        files={"image": ("upload.jpg", image_bytes, "image/jpeg")},
        timeout=30,
    )

    if up.status_code != 200:
        raise Exception(f"TikTok upload failed: {up.text}")

    upload_data = up.json()
    media_id = upload_data.get("data", {}).get("id")
    if not media_id:
        raise Exception(f"TikTok upload returned no media id: {up.text}")

    # Publication
    publish_url = "https://open.tiktokapis.com/v2/post/publish/"

    pub = requests.post(
        publish_url,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"},
        json={
            "post_info": {
                "title": (getattr(post, "content", "") or "Post")[:140],
            },
            "media_id": media_id,
        },
        timeout=30,
    )

    if pub.status_code != 200:
        raise Exception(f"TikTok publish failed: {pub.text}")

    return pub.json()
