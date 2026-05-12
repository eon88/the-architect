import logging
import datetime
import random
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from config import CORS_ORIGINS, configure_logging
from database import SessionLocal, User, PillarState, JournalEntry, UserFact, DailyRitual, PILLARS
from pipeline import ArchitectPipeline
from auth import create_session, get_current_user_id
from context import build_user_context

_STATIC_DIR = Path(__file__).parent / "static"

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="The Architect", version="0.2.0")
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
# Seed questions — first 7 sessions are sequential (one per pillar), after
# that we target the most-neglected pillar dynamically.
# ---------------------------------------------------------------------------

_SEED_QUESTIONS: list[tuple[str, str]] = [
    ("Social",             "Who in your life actually pushes you to be better, and who is just taking up space?"),
    ("Financial",          "If your income vanished tomorrow, how many days could you survive?"),
    ("Spiritual",          "When was the last time you felt peace without a screen or distraction?"),
    ("Craft/Career",       "What is one skill you'd spend 10,000 hours mastering just for the pride of it?"),
    ("Emotional/Intimacy", "Do the people closest to you feel truly seen and heard by you?"),
    ("Intellectual",       "What is a belief you held for years that you now know is wrong?"),
    ("Legacy",             "If you disappeared tomorrow, what would the world actually miss?"),
]


_MIDDAY_CHALLENGES: dict[str, str] = {
    "Social":             "Who haven't you reached out to in the last two weeks that you've been meaning to? Send the message right now — not later.",
    "Financial":          "Open your banking app. Look at the last 7 days of spending. What purchase would you take back?",
    "Spiritual":          "Put the phone down for 10 minutes. No screen, no music, no podcast. Just sit. Can you actually do it?",
    "Craft/Career":       "What is the one task you have been avoiding today? Stop reading this and go do it first.",
    "Emotional/Intimacy": "Think of the person closest to you. When did you last say something real to them — not small talk, not logistics?",
    "Intellectual":       "What is one idea you have been meaning to explore? You have 15 minutes. Start now.",
    "Legacy":             "What have you done today that your future self would be grateful for? If the answer is nothing — you still have time.",
}


def _get_priority_pillar(pillar_states: list[dict]) -> str:
    paused = [p for p in pillar_states if p["status"] == "Paused"]
    if paused:
        return max(paused, key=lambda p: p["days_in_state"])["name"]
    if pillar_states:
        return min(pillar_states, key=lambda p: p["days_in_state"])["name"]
    return "Social"


def _compute_streak(user_id: int, db: Session) -> int:
    entries = db.query(JournalEntry.timestamp).filter(JournalEntry.user_id == user_id).all()
    if not entries:
        return 0
    dates = {e.timestamp.date() for e in entries}
    today = datetime.datetime.utcnow().date()
    start = today if today in dates else today - datetime.timedelta(days=1)
    if start not in dates:
        return 0
    streak = 0
    current = start
    while current in dates:
        streak += 1
        current -= datetime.timedelta(days=1)
    return streak


def _get_seed_question(entry_count: int, pillar_states: list[dict]) -> str:
    if entry_count < len(_SEED_QUESTIONS):
        return _SEED_QUESTIONS[entry_count][1]

    # After baseline is built, target the most-neglected paused pillar
    paused = [p for p in pillar_states if p["status"] == "Paused"]
    if paused:
        most_neglected = max(paused, key=lambda p: p["days_in_state"])
        for pillar, question in _SEED_QUESTIONS:
            if pillar == most_neglected["name"]:
                return question

    return random.choice(_SEED_QUESTIONS)[1]


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
    has_onboarded: bool


class OnboardRequest(BaseModel):
    spark: str

    @field_validator("spark")
    @classmethod
    def spark_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Response must not be blank")
        if len(v) > 2000:
            raise ValueError("Response is too long (max 2,000 characters)")
        return v


class MiddayResponse(BaseModel):
    pillar: str
    challenge: str


class MorningRitualResponse(BaseModel):
    message: str
    directive: str
    seed_question: str
    streak: int
    total_entries: int


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


class WeeklyReviewResponse(BaseModel):
    moved: list[str]
    stalled: list[str]
    pattern: str
    directive: str
    entries_this_week: int


class MonthlyReviewResponse(BaseModel):
    pillars_moved: list[str]
    pillars_neglected: list[str]
    blind_spot: str
    architectural_decision: str
    entries_this_month: int


class MilestoneEntry(BaseModel):
    date: str
    momentum: str


class PillarMilestone(BaseModel):
    name: str
    status: str
    days_in_state: int
    entries: list[MilestoneEntry]


class FactResponse(BaseModel):
    id: int
    content: str
    created_at: str


class PillarResponse(BaseModel):
    name: str
    status: str
    days_in_state: int


class HealthResponse(BaseModel):
    status: str


# ---------------------------------------------------------------------------
# Dependencies
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
    return LoginResponse(user_id=user.id, email=user.email, token=token, has_onboarded=user.has_onboarded)


@app.post("/user/onboard", tags=["user"])
async def onboard_user(
    data: OnboardRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    if user.has_onboarded:
        raise HTTPException(status_code=400, detail="Already onboarded")

    # Run through the pipeline to extract pillar signal and facts
    result = pipeline.process_journal(data.spark)
    new_facts = pipeline.extract_facts(data.spark, [])

    # Store the Single Spark as a journal entry so morning ritual has context
    entry = JournalEntry(
        user_id=user.id,
        content=data.spark,
        pillar_associated=result["pillar"],
    )
    db.add(entry)

    # Set initial pillar momentum from the spark analysis
    pillar = (
        db.query(PillarState)
        .filter(PillarState.user_id == user.id, PillarState.pillar_name == result["pillar"])
        .first()
    )
    if pillar:
        pillar.status = result["momentum"]
        pillar.last_updated = datetime.datetime.utcnow()

    # Store extracted facts
    for fact in new_facts:
        db.add(UserFact(user_id=user.id, content=fact))

    user.has_onboarded = True
    db.commit()

    logger.info("User onboarded: user_id=%d, pillar=%s", user.id, result["pillar"])
    return {"status": "complete", "pillar": result["pillar"]}


@app.get("/ritual/morning", response_model=MorningRitualResponse, tags=["ritual"])
async def get_morning_ritual(user: User = Depends(require_user), db: Session = Depends(get_db)):
    today = datetime.date.today().isoformat()
    streak = _compute_streak(user.id, db)
    ctx = build_user_context(user.id, db)
    seed_question = _get_seed_question(ctx.entry_count, ctx.pillar_states)

    # Return cached story if one was already generated today
    cached = (
        db.query(DailyRitual)
        .filter(DailyRitual.user_id == user.id, DailyRitual.date == today)
        .first()
    )
    if cached:
        logger.info("Returning cached daily ritual for user_id=%d date=%s", user.id, today)
        return MorningRitualResponse(
            message=cached.message,
            directive=cached.directive,
            seed_question=seed_question,
            streak=streak,
            total_entries=ctx.entry_count,
        )

    if not ctx.recent_entries:
        message = "Welcome to Day 1. Your journey begins with a single step. Go do one thing today that the man you want to be would do."
        directive = "Write your first journal entry tonight — that is the only task that matters today."
    else:
        result = pipeline.process_journal(ctx.recent_entries[0], ctx)
        message = result["message"]
        directive = result["directive"]

    db.add(DailyRitual(user_id=user.id, date=today, message=message, directive=directive))
    db.commit()
    logger.info("Generated and cached daily ritual for user_id=%d date=%s", user.id, today)

    return MorningRitualResponse(
        message=message,
        directive=directive,
        seed_question=seed_question,
        streak=streak,
        total_entries=ctx.entry_count,
    )


@app.get("/ritual/midday", response_model=MiddayResponse, tags=["ritual"])
async def get_midday(user: User = Depends(require_user), db: Session = Depends(get_db)):
    ctx = build_user_context(user.id, db)
    pillar = _get_priority_pillar(ctx.pillar_states)
    return MiddayResponse(pillar=pillar, challenge=_MIDDAY_CHALLENGES[pillar])


@app.post("/ritual/evening", response_model=JournalResponse, tags=["ritual"])
async def submit_evening_journal(
    data: JournalRequest,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    # Build context BEFORE adding today's entry so the pipeline sees prior history
    ctx = build_user_context(user.id, db)

    result = pipeline.process_journal(data.content, ctx)

    # Persist journal entry
    entry = JournalEntry(
        user_id=user.id,
        content=data.content,
        pillar_associated=result["pillar"],
        momentum=result["momentum"],
    )
    db.add(entry)

    # Update pillar state
    pillar = (
        db.query(PillarState)
        .filter(PillarState.user_id == user.id, PillarState.pillar_name == result["pillar"])
        .first()
    )
    if pillar:
        pillar.status = result["momentum"]
        pillar.last_updated = datetime.datetime.utcnow()

    db.commit()

    # Extract and store new facts (runs after commit so entry is saved)
    new_facts = pipeline.extract_facts(data.content, ctx.user_facts)
    if new_facts:
        for fact in new_facts:
            db.add(UserFact(user_id=user.id, content=fact))
        db.commit()
        logger.info("Stored %d new fact(s) for user_id=%d", len(new_facts), user.id)

    logger.info("Evening journal processed for user_id=%d, pillar=%s", user.id, result["pillar"])
    return JournalResponse(
        status="success",
        pillar_updated=result["pillar"],
        momentum=result["momentum"],
    )


@app.get("/ritual/weekly", response_model=WeeklyReviewResponse, tags=["ritual"])
async def get_weekly_review(user: User = Depends(require_user), db: Session = Depends(get_db)):
    since = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    recent = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.timestamp >= since)
        .order_by(JournalEntry.timestamp.asc())
        .all()
    )

    ctx = build_user_context(user.id, db)

    if not recent:
        return WeeklyReviewResponse(
            moved=["No entries this week yet."],
            stalled=["All pillars — nothing to review without journal entries."],
            pattern="Come back after you've written a few entries this week.",
            directive="Write your first entry tonight.",
            entries_this_week=0,
        )

    entries = [
        {"date": e.timestamp.strftime("%A %d %b"), "content": e.content}
        for e in recent
    ]

    result = pipeline.generate_weekly_review(entries, ctx)
    return WeeklyReviewResponse(**result, entries_this_week=len(recent))


@app.get("/ritual/monthly", response_model=MonthlyReviewResponse, tags=["ritual"])
async def get_monthly_review(user: User = Depends(require_user), db: Session = Depends(get_db)):
    since = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    recent = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.timestamp >= since)
        .order_by(JournalEntry.timestamp.asc())
        .all()
    )

    ctx = build_user_context(user.id, db)

    if not recent:
        return MonthlyReviewResponse(
            pillars_moved=["No entries this month yet."],
            pillars_neglected=["All pillars — nothing to assess without journal entries."],
            blind_spot="Come back after you've built a foundation of entries. The patterns need data.",
            architectural_decision="Write your first journal entry tonight.",
            entries_this_month=0,
        )

    entries = [
        {"date": e.timestamp.strftime("%A %d %b"), "content": e.content}
        for e in recent
    ]

    result = pipeline.generate_monthly_review(entries, ctx)
    return MonthlyReviewResponse(**result, entries_this_month=len(recent))


@app.get("/user/facts", response_model=list[FactResponse], tags=["user"])
async def get_user_facts(user: User = Depends(require_user), db: Session = Depends(get_db)):
    facts = (
        db.query(UserFact)
        .filter(UserFact.user_id == user.id)
        .order_by(UserFact.created_at.desc())
        .all()
    )
    return [
        FactResponse(
            id=f.id,
            content=f.content,
            created_at=f.created_at.strftime("%d %b %Y"),
        )
        for f in facts
    ]


@app.delete("/user/facts/{fact_id}", tags=["user"])
async def delete_user_fact(
    fact_id: int,
    user: User = Depends(require_user),
    db: Session = Depends(get_db),
):
    fact = db.query(UserFact).filter(UserFact.id == fact_id).first()
    if not fact:
        raise HTTPException(status_code=404, detail="Fact not found")
    if fact.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your fact")
    db.delete(fact)
    db.commit()
    return {"status": "deleted"}


@app.get("/user/milestones", response_model=list[PillarMilestone], tags=["user"])
async def get_milestones(user: User = Depends(require_user), db: Session = Depends(get_db)):
    since = datetime.datetime.utcnow() - datetime.timedelta(days=28)
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.timestamp >= since)
        .order_by(JournalEntry.timestamp.asc())
        .all()
    )

    # Build per-pillar entry map: pillar -> {date_str -> momentum}
    pillar_days: dict[str, dict[str, str]] = {p: {} for p in PILLARS}
    for e in entries:
        if e.pillar_associated and e.pillar_associated in pillar_days:
            date_str = e.timestamp.strftime("%Y-%m-%d")
            pillar_days[e.pillar_associated][date_str] = e.momentum or "Paused"

    now = datetime.datetime.utcnow()
    pillar_states = db.query(PillarState).filter(PillarState.user_id == user.id).all()
    state_map = {p.pillar_name: p for p in pillar_states}

    result = []
    for pillar in PILLARS:
        ps = state_map.get(pillar)
        days_in_state = max(0, (now - ps.last_updated).days) if ps else 0
        history = [
            MilestoneEntry(date=d, momentum=m)
            for d, m in sorted(pillar_days[pillar].items())
        ]
        result.append(PillarMilestone(
            name=pillar,
            status=ps.status if ps else "Paused",
            days_in_state=days_in_state,
            entries=history,
        ))
    return result


@app.get("/user/pillars", response_model=list[PillarResponse], tags=["user"])
async def get_pillars(user: User = Depends(require_user), db: Session = Depends(get_db)):
    pillars = db.query(PillarState).filter(PillarState.user_id == user.id).all()
    if not pillars:
        for pillar in PILLARS:
            db.add(PillarState(user_id=user.id, pillar_name=pillar, status="Paused"))
        db.commit()
        pillars = db.query(PillarState).filter(PillarState.user_id == user.id).all()
    now = datetime.datetime.utcnow()
    return [
        PillarResponse(
            name=p.pillar_name,
            status=p.status,
            days_in_state=max(0, (now - p.last_updated).days),
        )
        for p in pillars
    ]
