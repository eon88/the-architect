import secrets
import logging
from typing import Optional
from fastapi import HTTPException, Header

logger = logging.getLogger(__name__)

# In-memory session store: token -> user_id
# Acceptable for MVP; replace with Redis or DB-backed sessions before scaling.
_sessions: dict[str, int] = {}


def create_session(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    _sessions[token] = user_id
    logger.info("Session created for user_id=%d", user_id)
    return token


def destroy_session(token: str) -> None:
    _sessions.pop(token, None)


def get_current_user_id(authorization: Optional[str] = Header(None)) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization[len("Bearer "):]
    user_id = _sessions.get(token)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user_id
