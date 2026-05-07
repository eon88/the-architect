from fastapi import FastAPI, Depends, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from database import SessionLocal, User, PillarState, JournalEntry
from pipeline import ArchitectPipeline
import datetime

app = FastAPI()
pipeline = ArchitectPipeline()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Serve static files (the frontend)
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def read_index():
    return FileResponse("static/index.html")

# --- API Endpoints ---

@app.post("/auth/login")
async def login(data: dict, db: Session = Depends(get_db)):
    email = data.get("email")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, full_name=data.get("name", "Architect"))
        db.add(user)
        db.commit()
        db.refresh(user)
        # Initialize pillars for new user
        pillars = ["Social", "Financial", "Spiritual", "Craft/Career", "Emotional/Intimacy", "Intellectual", "Legacy"]
        for p in pillars:
            db.add(PillarState(user_id=user.id, pillar_name=p, status="Paused"))
        db.commit()
    return {"user_id": user.id, "email": user.email}

@app.get("/ritual/morning/{user_id}")
async def get_morning_ritual(user_id: int, db: Session = Depends(get_db)):
    # Get the most recent journal entry to generate a story
    entry = db.query(JournalEntry).filter(JournalEntry.user_id == user_id).order_by(JournalEntry.timestamp.desc()).first()
    
    if not entry:
        return {"message": "Welcome to Day 1. Your journey begins with a single step. Go do one thing today that the man you want to be would do."}
    
    # Run the pipeline on the last entry
    result = pipeline.process_journal(entry.content)
    return {"message": result["message"]}

@app.post("/ritual/evening")
async def submit_evening_journal(data: dict, db: Session = Depends(get_db)):
    user_id = data.get("user_id")
    content = data.get("content")
    
    # Save the journal entry
    entry = JournalEntry(user_id=user_id, content=content)
    db.add(entry)
    
    # Process with pipeline to update pillar status
    result = pipeline.process_journal(content)
    
    # Update pillar state
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
