from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from productization.auth import AuthError, decode_access_token, get_auth_service


class SendCodeRequest(BaseModel):
    phone: str


class VerifyCodeRequest(BaseModel):
    phone: str
    code: str


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/send-code")
def send_code_endpoint(request: SendCodeRequest) -> dict:
    try:
        return get_auth_service().send_code(phone=request.phone)
    except AuthError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/verify")
def verify_code_endpoint(request: VerifyCodeRequest) -> dict:
    try:
        return get_auth_service().verify_code(phone=request.phone, code=request.code)
    except AuthError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def current_user_id(
    x_user_token: str | None = Header(default=None, alias="X-User-Token"),
    x_user_id: str | None = Header(default=None, alias="X-User-Id"),
) -> str:
    if x_user_token:
        try:
            return str(decode_access_token(x_user_token)["user_id"])
        except AuthError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc
    if x_user_id:
        return x_user_id
    raise HTTPException(status_code=401, detail="Missing authentication token.")
