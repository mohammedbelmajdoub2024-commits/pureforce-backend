import os
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

JWT_SECRET = os.getenv("JWT_SECRET", "supersecretkey")
ALGORITHM = "HS256"

security = HTTPBearer()


def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    token = credentials.credentials

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
