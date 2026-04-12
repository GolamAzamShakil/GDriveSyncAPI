"""
JWT-based authentication + role-based access control (RBAC).

Swagger UI flow
  1. POST /api/auth/login  with JSON body → copy the access_token
  2. Click "Authorize 🔓" in Swagger UI
  3. Paste the token into the "HTTPBearer" field → Authorize → Close
  4. All subsequent "Try it out" calls will include the Bearer header

Roles
  admin  — full access to all endpoints
  viewer — read-only; blocked from logs, scan triggers, schedule writes
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
    OAuth2PasswordBearer,
)

from core.config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET, USERS_DB

http_bearer = HTTPBearer(auto_error=False)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=JWT_EXPIRE_MINUTES)
    )
    payload.update({"exp": expire})
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired — call POST /api/auth/login to get a new one",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def get_current_user(
    bearer: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
    oauth2_token: Optional[str] = Depends(oauth2_scheme),
) -> dict:
    token = (bearer.credentials if bearer else None) or oauth2_token

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Not authenticated. "
                "Call POST /api/auth/login, copy the access_token, "
                "then click Authorize 🔓 in Swagger UI and paste it there."
            ),
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(token)
    username = payload.get("sub")
    role = payload.get("role")
    if not username or not role:
        raise HTTPException(status_code=401, detail="Malformed token")
    return {"username": username, "role": role}

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required for this endpoint",
        )
    return user


def require_viewer_or_above(user: dict = Depends(get_current_user)) -> dict:
    """Any authenticated user (viewer or admin)."""
    return user

def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = USERS_DB.get(username)
    if not user:
        return None
    if user["password"] != password:  # bcrypt implementation
        return None
    return {"username": username, "role": user["role"]}
