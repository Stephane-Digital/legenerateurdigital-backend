import requests


def _get_ig_user_id(access_token: str) -> str:
    """Resolve Instagram Business Account ID from a user/page token."""

    # 1) Get pages
    pages = requests.get(
        "https://graph.facebook.com/v19.0/me/accounts",
        params={"access_token": access_token},
        timeout=30,
    )
    if pages.status_code != 200:
        raise Exception(f"Instagram Graph: cannot list pages: {pages.text}")

    data = pages.json().get("data") or []
    if not data:
        raise Exception("Instagram Graph: no Facebook Pages available for this token")

    page_id = data[0].get("id")
    if not page_id:
        raise Exception("Instagram Graph: page id missing")

    # 2) Get IG business account linked
    page = requests.get(
        f"https://graph.facebook.com/v19.0/{page_id}",
        params={"fields": "instagram_business_account", "access_token": access_token},
        timeout=30,
    )
    if page.status_code != 200:
        raise Exception(f"Instagram Graph: cannot fetch page IG account: {page.text}")

    ig = (page.json() or {}).get("instagram_business_account") or {}
    ig_id = ig.get("id")
    if not ig_id:
        raise Exception("Instagram Graph: instagram_business_account not found (need IG business connected)")

    return ig_id


def publish_instagram(post, account):
    """
    Instagram Content Publishing API requires a *publicly accessible* image_url.

    Supported input on `post`:
      - post.content (caption)
      - post.image_url (preferred)

    If only image_base64 is provided, we raise a clear error (upload needs hosting).
    """

    access_token = account.access_token

    image_url = getattr(post, "image_url", None)
    image_base64 = getattr(post, "image_base64", None)

    if not image_url:
        # Instagram Graph doesn't accept raw bytes for photo publish.
        if image_base64:
            raise Exception(
                "Instagram publish requires image_url (public URL). "
                "Base64 upload is not supported by Instagram Graph API."
            )
        raise Exception("Instagram publish requires image_url")

    ig_user_id = _get_ig_user_id(access_token)

    # 1) Create media container
    create = requests.post(
        f"https://graph.facebook.com/v19.0/{ig_user_id}/media",
        data={
            "image_url": image_url,
            "caption": getattr(post, "content", "") or "",
            "access_token": access_token,
        },
        timeout=30,
    )

    if create.status_code != 200:
        raise Exception(f"Instagram create media failed: {create.text}")

    creation_id = (create.json() or {}).get("id")
    if not creation_id:
        raise Exception(f"Instagram create media returned no id: {create.text}")

    # 2) Publish
    pub = requests.post(
        f"https://graph.facebook.com/v19.0/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
        timeout=30,
    )

    if pub.status_code != 200:
        raise Exception(f"Instagram publish failed: {pub.text}")

    return pub.json()
