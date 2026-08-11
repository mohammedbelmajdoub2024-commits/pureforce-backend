import firebase_admin
from firebase_admin import credentials, auth
from fastapi import Header, HTTPException
import os
import json
import logging

logger = logging.getLogger(__name__)

firebase_initialized = False

if os.getenv("FB_KEY_1") and os.getenv("FB_KEY_2") and os.getenv("FB_KEY_3"):
    try:
        raw = (
            os.environ["FB_KEY_1"]
            + os.environ["FB_KEY_2"]
            + os.environ["FB_KEY_3"]
        )

        cred_info = json.loads(raw)
        cred = credentials.Certificate(cred_info)

        firebase_admin.initialize_app(cred)
        firebase_initialized = True

        logger.info("Firebase initialized successfully")

    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")

else:
    logger.warning("Firebase credentials not found")


def verify_token(authorization: str = Header(None)):
    if not firebase_initialized:
        raise HTTPException(
            status_code=503,
            detail="Firebase is not configured on this server."
        )

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Token manquant"
        )

    token = authorization.split("Bearer ")[1]

    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou expiré"
        )
