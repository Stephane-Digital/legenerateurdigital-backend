import requests
import os
import urllib.parse

CLIENT_ID = os.getenv("LINKEDIN_CLIENT_ID")
CLIENT_SECRET = os.getenv("LINKEDIN_CLIENT_SECRET")
REDIRECT_URI = os.getenv("LINKEDIN_REDIRECT_URI")

def get_linkedin_auth_url():
    scope = "w_member_social,r_basicprofile"
    return (
        "https://www.linkedin.com/oauth/v2/authorization?"
        f"response_type=code&client_id={CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&scope={scope}"
    )

def exchange_linkedin_code(code: str):
    url = "https://www.linkedin.com/oauth/v2/accessToken"

    res = requests.post(
        url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )

    if res.status_code != 200:
        raise Exception("LinkedIn OAuth failed")

    d = res.json()
    return {
        "access_token": d["access_token"],
        "expires_in": d.get("expires_in"),
    }
