import os
import requests
import urllib.parse

INSTAGRAM_CLIENT_ID = os.getenv("INSTAGRAM_CLIENT_ID")
INSTAGRAM_CLIENT_SECRET = os.getenv("INSTAGRAM_CLIENT_SECRET")
INSTAGRAM_REDIRECT_URI = os.getenv("INSTAGRAM_REDIRECT_URI")

# Scopes Instagram Graph (publication)
# https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/
SCOPES = [
    "instagram_basic",
    "instagram_content_publish",
    "pages_show_list",
    "pages_read_engagement",
]

def get_instagram_auth_url():
    """
    Retourne l’URL d’authorization OAuth Instagram (via Facebook Login).
    """
    scope_str = ",".join(SCOPES)

    params = {
        "client_id": INSTAGRAM_CLIENT_ID,
        "redirect_uri": INSTAGRAM_REDIRECT_URI,
        "scope": scope_str,
        "response_type": "code",
    }

    return "https://www.facebook.com/v19.0/dialog/oauth?" + urllib.parse.urlencode(params)


def exchange_instagram_code(code: str):
    """
    Échange le code OAuth contre access_token long-lived.
    Flow:
    1) Facebook OAuth -> short-lived token
    2) Exchange -> long-lived token
    """
    # 1) Short-lived token
    token_url = "https://graph.facebook.com/v19.0/oauth/access_token"
    res = requests.get(token_url, params={
        "client_id": INSTAGRAM_CLIENT_ID,
        "client_secret": INSTAGRAM_CLIENT_SECRET,
        "redirect_uri": INSTAGRAM_REDIRECT_URI,
        "code": code,
    })

    if res.status_code != 200:
        raise Exception(f"Instagram OAuth short-lived failed: {res.text}")

    short_token = res.json()["access_token"]

    # 2) Long-lived token
    long_url = "https://graph.facebook.com/v19.0/oauth/access_token"
    long_res = requests.get(long_url, params={
        "grant_type": "fb_exchange_token",
        "client_id": INSTAGRAM_CLIENT_ID,
        "client_secret": INSTAGRAM_CLIENT_SECRET,
        "fb_exchange_token": short_token,
    })

    if long_res.status_code != 200:
        raise Exception(f"Instagram OAuth long-lived failed: {long_res.text}")

    d = long_res.json()

    return {
        "access_token": d["access_token"],
        "expires_in": d.get("expires_in"),
    }
