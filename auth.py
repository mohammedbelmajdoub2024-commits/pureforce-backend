import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Header, HTTPException
import os

import json

cred_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
if os.path.exists(cred_path):
    cred = credentials.Certificate(cred_path)
    firebase_admin.initialize_app(cred)
elif os.getenv("FIREBASE_SERVICE_ACCOUNT"):
    try:
        cred_info = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"))
        cred = credentials.Certificate(cred_info)
        firebase_admin.initialize_app(cred)
    except Exception as e:
        raise RuntimeError(f"Failed to load Firebase credentials from environment variable: {e}")
else:
    raise FileNotFoundError("Firebase credentials not found (neither serviceAccountKey.json nor FIREBASE_SERVICE_ACCOUNT env var exists)")

def verify_token(authorization: str = Header(None)):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")

    token = authorization.split("Bearer ")[1]

    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")