from __future__ import annotations
import os
from typing import Optional
import jwt as pyjwt
from fastapi import Header

try:
    import firebase_admin
    from firebase_admin import auth as fb_auth, credentials
    _svc_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH","")
    if _svc_path and not firebase_admin._apps:
        cred = credentials.Certificate(_svc_path)
        firebase_admin.initialize_app(cred)
    FIREBASE_OK = bool(firebase_admin._apps)
except ImportError:
    FIREBASE_OK = False

LINKEDIN_JWT_SECRET = os.getenv("LINKEDIN_JWT_SECRET","change-me-in-production")
LINKEDIN_JWT_ALG = "HS256"

def create_linkedin_token(uid: str, email: str, name: str) -> str:
    return pyjwt.encode({"uid":uid,"email":email,"name":name,"provider":"linkedin"}, LINKEDIN_JWT_SECRET, algorithm=LINKEDIN_JWT_ALG)

def _verify_linkedin_token(token: str) -> Optional[dict]:
    try:
        payload = pyjwt.decode(token, LINKEDIN_JWT_SECRET, algorithms=[LINKEDIN_JWT_ALG])
        return {"uid": payload.get("uid"), "name": payload.get("name"), "email": payload.get("email")}
    except Exception:
        return None

async def get_current_user(authorization: Optional[str] = Header(None)) -> Optional[dict]:
    if not authorization or not authorization.startswith("Bearer "): return None
    token = authorization[7:]
    if not token.startswith("eyJ") or len(token) < 200:
        return _verify_linkedin_token(token)
    if FIREBASE_OK:
        try:
            decoded = fb_auth.verify_id_token(token)
            return {"uid": decoded.get("uid"), "name": decoded.get("name"), "email": decoded.get("email")}
        except Exception:
            pass
    return _verify_linkedin_token(token)

async def get_current_uid(authorization: Optional[str] = Header(None)) -> Optional[str]:
    user = await get_current_user(authorization)
    return user["uid"] if user else None
