from fastapi import Request, HTTPException, status
from jose import jwt, JWTError
import os

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-it-in-prod")
ALGORITHM = "HS256"

async def verify_jwt(request: Request):
    auth_header = request.headers.get("Authorization")
    token = None
    
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    else:
        # Fallback to query parameter for SSE and other browser-direct requests
        # Support both 'token' (web-client) and 'access_token' (legacy/standard)
        token = request.query_params.get("token") or request.query_params.get("access_token")
        
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        user_id: str = payload.get("user_id")
        if username is None or user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )
        # Store for downstream use
        request.state.user_id = user_id
        request.state.username = username
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
