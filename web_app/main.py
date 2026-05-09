from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, User, PillarState, JournalEntry
from pipeline import ArchitectPipeline
import datetime
import hashlib
import os
import base64

app = FastAPI()
pipeline = ArchitectPipeline()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
    return base64.b64encode(salt + key).decode()

def _verify_password(password: str, stored: str) -> bool:
    try:
        decoded = base64.b64decode(stored.encode())
        salt, stored_key = decoded[:16], decoded[16:]
        key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260_000)
        return key == stored_key
    except Exception:
        return False

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# --- API Endpoints ---

@app.post("/auth/register")
async def register(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    name = data.get("name", "Architect").strip()
    password = data.get("password", "")

    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(email=email, full_name=name or "Architect", password_hash=_hash_password(password))
    db.add(user)
    db.commit()
    db.refresh(user)

    pillars = ["Social", "Financial", "Spiritual", "Craft/Career", "Emotional/Intimacy", "Intellectual", "Legacy"]
    for p in pillars:
        db.add(PillarState(user_id=user.id, pillar_name=p, status="Paused"))
    db.commit()

    return {"user_id": user.id, "name": user.full_name, "email": user.email}

@app.post("/auth/login")
async def login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")

    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password are required")

    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not _verify_password(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Wrong email or password")

    return {"user_id": user.id, "name": user.full_name, "email": user.email}

@app.get("/ritual/morning/{user_id}")
async def get_morning_ritual(user_id: int, db: Session = Depends(get_db)):
    entry = db.query(JournalEntry).filter(JournalEntry.user_id == user_id).order_by(JournalEntry.timestamp.desc()).first()

    if not entry:
        return {"message": "Welcome to Day 1. Your journey begins with a single step. Go do one thing today that the man you want to be would do."}

    result = pipeline.process_journal(entry.content)
    return {"message": result["message"]}

@app.post("/ritual/evening")
async def submit_evening_journal(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("user_id")
    content = data.get("content")

    entry = JournalEntry(user_id=user_id, content=content)
    db.add(entry)

    result = pipeline.process_journal(content)

    pillar = db.query(PillarState).filter(
        PillarState.user_id == user_id,
        PillarState.pillar_name == result["pillar"]
    ).first()
    if pillar:
        pillar.status = result["momentum"]
        pillar.last_updated = datetime.datetime.utcnow()
    db.commit()

    return {"status": "success", "pillar_updated": result["pillar"], "momentum": result["momentum"]}

@app.get("/user/pillars/{user_id}")
async def get_pillars(user_id: int, db: Session = Depends(get_db)):
    pillars = db.query(PillarState).filter(PillarState.user_id == user_id).all()
    return [{"name": p.pillar_name, "status": p.status} for p in pillars]
