import logging
import datetime
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from config import CORS_ORIGINS, configure_logging
from database import SessionLocal, User, PillarState, JournalEntry, PILLARS
from pipeline import ArchitectPipeline
from auth import create_session, get_current_user_id

_STATIC_DIR = Path(__file__).parent / "static"

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="The Architect", version="0.1.0")
pipeline = ArchitectPipeline()

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    name: str = "Architect"

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("name must not be blank")
        return v[:200]


class LoginResponse(BaseModel):
    user_id: int
    email: str
    token: str


class MorningRitualResponse(BaseModel):
    message: str


class JournalRequest(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Journal entry must not be blank")
        if len(v) > 10_000:
            raise ValueError("Journal entry is too long (max 10,000 characters)")
        return v


class JournalResponse(BaseModel):
    status: str
    pillar_updated: str
    momentum: str


class PillarResponse(BaseModel):
    name: str
    status: str


class HealthResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def require_user(
    user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
async def read_index():
    return FileResponse(str(_STATIC_DIR / "index.html"))


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    return {"status": "ok"}


@app.post("/auth/login", response_model=LoginResponse, tags=["auth"])
async def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user:
        user = User(email=data.email, full_name=data.name)
        db.add(user)
        db.flush()
        for pillar in PILLARS:
            db.add(PillarState(user_id=user.id, pillar_name=pillar, status="Paused"))
        db.commit()
        db.refresh(user)
        logger.info("New user registered: %s", data.email)
    else:
        logger.info("Existing user logged in: %s", data.email)

    token = create_session(user.id)
    return LoginResponse(user_id=user.id, email=user.email, token=token)


@app.get("/ritual/morning", response_model=MorningRitualResponse, tags=["ritual"])
async def get_morning_ritual(user: User = Depends(require_user), db: Session = Depends(get_db)):
    entry = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id)
        .order_by(JournalEntry.timestamp.desc())
        .first()
    )

    if not entry:
        return MorningRitualResponse(
            message="Welcome to Day 1. Your journey begins with a single step. Go do one thing today that the man you want to be would do."
        )

    result = pipeline.process_journal(entry.content)
    return MorningRitualResponse(message=result["message"])


@app.post("/ritual/evening", response_model=JournalResponse, tags=["ritual"])
async def submit_evening_journal(
    data: JournalRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    result = pipeline.process_journal(data.content)

    entry = JournalEntry(
        user_id=user.id,
        content=data.content,
        pillar_associated=result["pillar"],
    )
    db.add(entry)

    pillar = (
        db.query(PillarState)
        .filter(PillarState.user_id == user.id, PillarState.pillar_name == result["pillar"])
        .first()
    )
    if pillar:
        pillar.status = result["momentum"]
        pillar.last_updated = datetime.datetime.utcnow()

    db.commit()
    logger.info("Evening journal processed for user_id=%d, pillar=%s", user.id, result["pillar"])

    return JournalResponse(
        status="success",
        pillar_updated=result["pillar"],
        momentum=result["momentum"],
    )


@app.get("/user/pillars", response_model=list[PillarResponse], tags=["user"])
async def get_pillars(user: User = Depends(require_user), db: Session = Depends(get_db)):
    pillars = db.query(PillarState).filter(PillarState.user_id == user.id).all()
    return [PillarResponse(name=p.pillar_name, status=p.status) for p in pillars]
