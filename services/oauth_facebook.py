import requests
import os

CLIENT_ID = os.getenv("FACEBOOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("FACEBOOK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("FACEBOOK_REDIRECT_URI")

def get_facebook_auth_url():
    return (
        "https://www.facebook.com/v19.0/dialog/oauth?"
        f"client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        "&scope=pages_show_list,pages_read_engagement,pages_manage_posts"
    )

def exchange_facebook_code(code: str):
    url = (
        "https://graph.facebook.com/v19.0/oauth/access_token?"
        f"client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&client_secret={CLIENT_SECRET}"
        f"&code={code}"
    )

    res = requests.get(url)

    if res.status_code != 200:
        raise Exception("Facebook OAuth failed")

    d = res.json()
    return {
        "access_token": d["access_token"],
        "expires_in": d.get("expires_in"),
    }
