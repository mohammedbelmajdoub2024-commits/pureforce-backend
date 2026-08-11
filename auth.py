import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Header, HTTPException
import os
import json
import logging

logger = logging.getLogger(__name__)

firebase_initialized = False

cred_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
if os.path.exists(cred_path):
    try:
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        firebase_initialized = True
        logger.info("Firebase initialized from serviceAccountKey.json")
    except Exception as e:
        logger.error(f"Failed to init Firebase from file: {e}")
elif os.getenv("FIREBASE_SERVICE_ACCOUNT"):
    try:
        cred_info = json.loads(os.getenv("FIREBASE_SERVICE_ACCOUNT"))
        cred = credentials.Certificate(cred_info)
        firebase_admin.initialize_app(cred)
        firebase_initialized = True
        logger.info("Firebase initialized from FIREBASE_SERVICE_ACCOUNT env var")
    except Exception as e:
        logger.error(f"Failed to load Firebase credentials from environment variable: {e}")
else:
    logger.warning(
        "Firebase credentials not found. "
        "Set FIREBASE_SERVICE_ACCOUNT env var on Railway. "
        "All authenticated endpoints will return 503 until this is fixed."
    )


def verify_token(authorization: str = Header(None)):
    if not firebase_initialized:
        raise HTTPException(
            status_code=503,
            detail="Firebase is not configured on this server. Set the FIREBASE_SERVICE_ACCOUNT environment variable."
        )

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token manquant")

    token = authorization.split("Bearer ")[1]

    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token
    except Exception:
        raise HTTPException(status_code=401, detail="Token invalide ou expiré")
