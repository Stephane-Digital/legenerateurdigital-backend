import requests
import base64


def publish_facebook(post, account):
    """
    Publie une image + texte sur Facebook via l'API Graph.

    Input expected on `post`:
      - post.content
      - post.image_base64 OR post.image_url

    Note: posting to /me requires a valid token scope; in practice you may want to post to a Page ID.
    """

    if not getattr(post, "image_base64", None) and not getattr(post, "image_url", None) and not getattr(post, "content", None):
        raise Exception("Rien à publier")

    access_token = account.access_token

    # 1) If image_url is provided, use url upload.
    if getattr(post, "image_url", None):
        upload_res = requests.post(
            "https://graph.facebook.com/v19.0/me/photos",
            data={
                "url": post.image_url,
                "caption": getattr(post, "content", "") or "",
                "access_token": access_token,
            },
            timeout=30,
        )
        if upload_res.status_code != 200:
            raise Exception(f"Facebook url upload failed: {upload_res.text}")
        return upload_res.json()

    # 2) Upload image bytes (base64)
    if getattr(post, "image_base64", None):
        img_bytes = base64.b64decode(post.image_base64)

        upload_res = requests.post(
            "https://graph.facebook.com/v19.0/me/photos",
            data={
                "caption": getattr(post, "content", "") or "",
                "access_token": access_token,
            },
            files={"source": img_bytes},
            timeout=30,
        )

        if upload_res.status_code != 200:
            raise Exception(f"Facebook upload failed: {upload_res.text}")

        return upload_res.json()

    # 3) Text-only post
    text_res = requests.post(
        "https://graph.facebook.com/v19.0/me/feed",
        data={
            "message": getattr(post, "content", "") or "",
            "access_token": access_token,
        },
        timeout=30,
    )

    if text_res.status_code != 200:
        raise Exception(f"Facebook text post failed: {text_res.text}")

    return text_res.json()
