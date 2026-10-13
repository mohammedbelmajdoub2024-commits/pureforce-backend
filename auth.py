import os
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET", "")
ALGORITHM = "HS256"

security = HTTPBearer()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

    if len(JWT_SECRET) < 32:
        raise HTTPException(status_code=503, detail="Authentication is not configured. Set a strong JWT_SECRET.")

    try:
        decoded_token = jwt.decode(
            token,
            JWT_SECRET,
            algorithms=[ALGORITHM]
        )

        return decoded_token

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expiré"
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou expiré"
        )
