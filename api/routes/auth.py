"""
Endpoints
POST /api/auth/login   — JSON body  → JWT  (for API clients / fetch calls)
POST /api/auth/token   — Form body  → JWT  (for Swagger UI Authorize dialog)
GET  /api/auth/me      — returns current user info

Swagger UI authorization flow
Option A — manual (always works, two steps):
  1. POST /api/auth/login  (Try it out → Execute)  → copy access_token
  2. Click "Authorize 🔓" at top of page
     → paste token into the "HTTPBearer (http, Bearer)" field
     → click Authorize → Close

Option B — built-in Swagger lock (one step):
  1. Click "Authorize 🔓"
     → fill in username + password in the "OAuth2PasswordBearer" section
     → click Authorize
  This calls POST /api/auth/token (form-encoded) behind the scenes,
  and Swagger UI injects the returned token automatically.
"""

from datetime import timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from api.dependencies.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
)
from core.config import JWT_EXPIRE_MINUTES
from models.schemas import LoginRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["Auth"])

def _issue_token(username: str, password: str) -> TokenResponse:
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(
        {"sub": user["username"], "role": user["role"]},
        expires_delta=timedelta(minutes=JWT_EXPIRE_MINUTES),
    )
    return TokenResponse(
        access_token=token,
        role=user["role"],
        expires_in=JWT_EXPIRE_MINUTES * 60,
    )

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Obtain a JWT  —  JSON body",
    description=(
        "Send `username` and `password` as a JSON body. "
        "Returns a Bearer token to include in the `Authorization` header "
        "for all subsequent requests.\n\n"
        "**Swagger UI tip:** after calling this, copy the `access_token`, "
        "click **Authorize 🔓** at the top of this page, paste the token "
        "into the **HTTPBearer** field, and click Authorize."
    ),
)
def login(body: LoginRequest):
    return _issue_token(body.username, body.password)

@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Obtain a JWT  —  form body",
    description=(
        "Accepts `username` and `password` as **form fields** "
        "(application/x-www-form-urlencoded). "
        "This is the endpoint that Swagger UI calls when you click "
        "**Authorize 🔓** and fill in the username/password fields. "
        "You do not need to call this manually."
    ),
    include_in_schema=True,
)
def token_form(form: OAuth2PasswordRequestForm = Depends()):
    return _issue_token(form.username, form.password)

@router.get(
    "/me",
    summary="Return the currently authenticated user's info",
)
def me(user: dict = Depends(get_current_user)):
    return {"username": user["username"], "role": user["role"]}
