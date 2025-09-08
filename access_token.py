"""
Gets an OAuth2 access token from Gloo and returns Bearer headers.
Relies on environment variables: GLOO_CLIENT_ID, GLOO_CLIENT_SECRET.
"""

import base64
import os
import time
import requests
from dotenv import load_dotenv
import jwt  # PyJWT

load_dotenv()  # reads .env next to this file

CLIENT_ID = os.getenv("GLOO_CLIENT_ID")
CLIENT_SECRET = os.getenv("GLOO_CLIENT_SECRET")

def get_access_token(client_id: str, client_secret: str) -> dict:
    if not client_id or not client_secret:
        raise ValueError("GLOO_CLIENT_ID or GLOO_CLIENT_SECRET not set")
    auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    resp = requests.post(
        "https://platform.ai.gloo.com/oauth2/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {auth}",
        },
        data={"grant_type": "client_credentials", "scope": "api/access"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def get_bearer_header(client_id: str, client_secret: str) -> dict:
    token_data = get_access_token(client_id, client_secret)
    access_token = token_data["access_token"]
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
    }

if __name__ == "__main__":
    # Simple sanity check; avoids printing full secrets.
    token_data = get_access_token(CLIENT_ID, CLIENT_SECRET)
    access_token = token_data["access_token"]
    expires_at_epoch = int(time.time()) + int(token_data.get("expires_in", 3600))
    try:
        decoded = jwt.decode(
            access_token,
            options={"verify_signature": False},
            algorithms=["RS256", "HS256", "ES256"],
        )
        jwt_exp_epoch = decoded.get("exp")
    except Exception:
        jwt_exp_epoch = None

    print("Access token preview:", access_token[:32] + "...")
    remaining_sec = expires_at_epoch - int(time.time())
    print(f"Expires in {remaining_sec} seconds (~{remaining_sec // 60} minutes)")
