import requests
import os

CLIENT_ID = os.getenv("TIKTOK_CLIENT_ID")
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET")
REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI")

def get_tiktok_auth_url():
    return (
        "https://www.tiktok.com/v2/auth/authorize/"
        f"?client_key={CLIENT_ID}"
        f"&scope=user.info.basic,video.publish"
        f"&redirect_uri={REDIRECT_URI}"
        "&response_type=code"
    )

def exchange_tiktok_code(code: str):
    url = "https://open.tiktokapis.com/v2/oauth/token/"
    data = {
        "client_key": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    }

    res = requests.post(url, data=data)

    if res.status_code != 200:
        raise Exception("TikTok OAuth failed")

    d = res.json()
    return {
        "access_token": d["data"]["access_token"],
        "refresh_token": d["data"].get("refresh_token"),
        "expires_in": d["data"]["expires_in"],
    }
