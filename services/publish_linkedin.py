import requests
import base64


def publish_linkedin(post, account):
    access_token = account.access_token

    # Récupération de l'URN de la personne
    me = requests.get(
        "https://api.linkedin.com/v2/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )

    if me.status_code != 200:
        raise Exception(f"LinkedIn /me failed: {me.text}")

    user_urn = me.json().get("id")

    # ========================================
    # IMAGE UPLOAD
    # ========================================
    asset_urn = None

    image_url = getattr(post, "image_url", None)

    # If image_url provided: download then upload (LinkedIn needs binary upload)
    if image_url and not getattr(post, "image_base64", None):
        dl = requests.get(image_url, timeout=30)
        if dl.status_code != 200:
            raise Exception(f"LinkedIn download image failed: {dl.text}")
        post.image_base64 = base64.b64encode(dl.content).decode("utf-8")

    if getattr(post, "image_base64", None):
        register = requests.post(
            "https://api.linkedin.com/v2/assets?action=registerUpload",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={
                "registerUploadRequest": {
                    "owner": f"urn:li:person:{user_urn}",
                    "recipes": ["urn:li:digitalmediaRecipe:feedshare-image"],
                    "serviceRelationships": [
                        {"relationshipType": "OWNER", "identifier": "urn:li:userGeneratedContent"}
                    ],
                }
            },
            timeout=30,
        )

        if register.status_code != 200:
            raise Exception(f"LinkedIn register failed: {register.text}")

        upload_info = register.json()
        upload_url = upload_info["value"]["uploadMechanism"]["com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest"]["uploadUrl"]
        asset_urn = upload_info["value"]["asset"]

        # Upload image binaire
        image_bytes = base64.b64decode(post.image_base64)
        up = requests.put(
            upload_url,
            data=image_bytes,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "image/jpeg"},
            timeout=30,
        )

        if up.status_code not in (200, 201, 204):
            raise Exception(f"LinkedIn upload failed: {up.text}")

    # ========================================
    # PUBLICATION
    # ========================================
    payload = {
        "author": f"urn:li:person:{user_urn}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "shareCommentary": {"text": getattr(post, "content", "") or ""},
                "shareMediaCategory": "NONE" if not asset_urn else "IMAGE",
                "media": (
                    [
                        {
                            "status": "READY",
                            "description": {"text": getattr(post, "content", "") or ""},
                            "media": asset_urn,
                            "title": {"text": "Publication"},
                        }
                    ]
                    if asset_urn
                    else []
                ),
            }
        },
        "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
    }

    r = requests.post(
        "https://api.linkedin.com/v2/ugcPosts",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=30,
    )

    if r.status_code not in (200, 201):
        raise Exception(f"LinkedIn publish failed: {r.text}")

    return r.json()
