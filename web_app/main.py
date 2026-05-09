from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from passlib.context import CryptContext
from database import SessionLocal, User, PillarState, JournalEntry
from pipeline import ArchitectPipeline
import datetime

app = FastAPI()
pipeline = ArchitectPipeline()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PILLARS = ["Social", "Financial", "Spiritual", "Craft/Career", "Emotional/Intimacy", "Intellectual", "Legacy"]

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_pillars(db, user_id):
    for p in PILLARS:
        db.add(PillarState(user_id=user_id, pillar_name=p, status="Paused"))
    db.commit()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

@app.post("/auth/register")
async def register(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    if not email or not password:
        raise HTTPException(status_code=400, detail="Email and password required")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=email,
        full_name=email.split("@")[0],
        password_hash=pwd_context.hash(password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    init_pillars(db, user.id)
    return {"user_id": user.id, "email": user.email}

@app.post("/auth/login")
async def login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user = db.query(User).filter(User.email == email).first()
    if not user or not user.password_hash or not pwd_context.verify(password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return {"user_id": user.id, "email": user.email}

@app.get("/ritual/morning/{user_id}")
async def get_morning_ritual(user_id: int, db: Session = Depends(get_db)):
    entry = db.query(JournalEntry).filter(JournalEntry.user_id == user_id).order_by(JournalEntry.timestamp.desc()).first()
    if not entry:
        return {"message": "Welcome to Day 1. Your journey begins with a single step. Go do one thing today that the man you want to be would do."}
    result = pipeline.process_journal(entry.content)
    return {"message": result["message"]}

@app.post("/ritual/evening")
async def submit_evening_journal(data: dict, db: Session = Depends(get_db)):
    user_id = int(data.get("user_id"))
    content = data.get("content")
    entry = JournalEntry(user_id=user_id, content=content)
    db.add(entry)
    db.commit()
    result = pipeline.process_journal(content)
    pillar = db.query(PillarState).filter(PillarState.user_id == user_id, PillarState.pillar_name == result["pillar"]).first()
    if pillar:
        pillar.status = result["momentum"]
        pillar.last_updated = datetime.datetime.utcnow()
        db.commit()
    return {"status": "success", "pillar_updated": result["pillar"], "momentum": result["momentum"]}

@app.get("/user/pillars/{user_id}")
async def get_pillars(user_id: int, db: Session = Depends(get_db)):
    pillars = db.query(PillarState).filter(PillarState.user_id == user_id).all()
    return [{"name": p.pillar_name, "status": p.status} for p in pillars]
