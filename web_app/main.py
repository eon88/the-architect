import json
import logging
import datetime
import calendar
import random
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from config import CORS_ORIGINS, configure_logging
from database import (
    SessionLocal, User, PillarState, JournalEntry, UserFact,
    DailyRitual, PillarTarget, MilestoneItem, WeeklyReview, MonthlyReview, PILLARS
)
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

class TargetCreate(BaseModel):
    pillar_name: str
    text: str

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Target text must not be blank")
        return v[:200]


class TargetUpdate(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in ("locked", "active", "done"):
            raise ValueError("Status must be locked, active, or done")
        return v


class MilestoneCreate(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def text_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Milestone text must not be blank")
        return v[:200]


class MilestoneToggle(BaseModel):
    status: str

    @field_validator("status")
    @classmethod
    def valid_status(cls, v: str) -> str:
        if v not in ("todo", "done"):
            raise ValueError("Status must be todo or done")
        return v


class MilestoneResponse(BaseModel):
    id: int
    target_id: int
    text: str
    status: str


class TargetResponse(BaseModel):
    id: int
    pillar_name: str
    text: str
    status: str
    milestone_count: int = 0
    milestones_done: int = 0


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


def _build_targets_context(user_id: int, db: Session) -> str:
    """Build a formatted string of active/locked targets with milestone progress."""
    targets = (
        db.query(PillarTarget)
        .filter(PillarTarget.user_id == user_id, PillarTarget.status != "done")
        .order_by(PillarTarget.pillar_name, PillarTarget.created_at)
        .all()
    )
    if not targets:
        return "No active targets set."
    lines = []
    for t in targets:
        milestones = (
            db.query(MilestoneItem)
            .filter(MilestoneItem.target_id == t.id)
            .order_by(MilestoneItem.created_at)
            .all()
        )
        done = sum(1 for m in milestones if m.status == "done")
        total = len(milestones)
        badge = f"({done}/{total} milestones done)" if total else "(no milestones)"
        lines.append(f"- [{t.pillar_name}] {t.text} — {t.status.upper()} {badge}")
        for m in milestones:
            icon = "✓" if m.status == "done" else "○"
            lines.append(f"    · {icon} {m.text}")
    return "\n".join(lines)


def _today() -> datetime.date:
    return datetime.date.today()


def _days_until_month_end() -> int:
    today = _today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return last_day - today.day


def _week_key_for_weekend() -> str:
    """ISO week key for the current Sat/Sun window (keyed to the Sunday)."""
    today = datetime.date.today()
    # Advance to the nearest upcoming or current Sunday
    days_to_sunday = (6 - today.weekday()) % 7
    sunday = today + datetime.timedelta(days=days_to_sunday)
    return sunday.isocalendar()[0:2]  # (year, week)


@app.get("/ritual/weekly", tags=["ritual"])
async def get_weekly_review(user: User = Depends(require_user), db: Session = Depends(get_db)):
    today = _today()
    weekday = today.weekday()  # 0=Mon … 5=Sat, 6=Sun

    if weekday < 5:  # Mon–Fri
        days_until = 5 - weekday
        return JSONResponse(
            status_code=425,
            content={"detail": "Weekly review available from Saturday", "days_until": days_until},
        )

    # Saturday or Sunday — compute week key (keyed to this Sunday)
    days_to_sunday = (6 - weekday) % 7
    sunday = today + datetime.timedelta(days=days_to_sunday)
    iso = sunday.isocalendar()
    week_key = f"{iso[0]}-W{iso[1]:02d}"

    cached = (
        db.query(WeeklyReview)
        .filter(WeeklyReview.user_id == user.id, WeeklyReview.week_key == week_key)
        .first()
    )
    if cached:
        return WeeklyReviewResponse(
            moved=json.loads(cached.moved),
            stalled=json.loads(cached.stalled),
            pattern=cached.pattern,
            directive=cached.directive,
            entries_this_week=cached.entries_count,
        )

    since = datetime.datetime.utcnow() - datetime.timedelta(days=7)
    recent = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.timestamp >= since)
        .order_by(JournalEntry.timestamp.asc())
        .all()
    )
    ctx = build_user_context(user.id, db)
    targets_ctx = _build_targets_context(user.id, db)

    if not recent:
        result = {
            "moved": ["No entries this week yet."],
            "stalled": ["All pillars — nothing to review without journal entries."],
            "pattern": "Come back after you've written a few entries this week.",
            "directive": "Write your first entry tonight.",
        }
    else:
        entries = [{"date": e.timestamp.strftime("%A %d %b"), "content": e.content} for e in recent]
        result = pipeline.generate_weekly_review(entries, ctx, targets_ctx)

    db.add(WeeklyReview(
        user_id=user.id,
        week_key=week_key,
        moved=json.dumps(result["moved"]),
        stalled=json.dumps(result["stalled"]),
        pattern=result["pattern"],
        directive=result["directive"],
        entries_count=len(recent),
    ))
    db.commit()
    logger.info("Generated and cached weekly review for user_id=%d week=%s", user.id, week_key)

    return WeeklyReviewResponse(**result, entries_this_week=len(recent))


@app.get("/ritual/monthly", tags=["ritual"])
async def get_monthly_review(user: User = Depends(require_user), db: Session = Depends(get_db)):
    days_left = _days_until_month_end()

    if days_left > 1:
        return JSONResponse(
            status_code=425,
            content={"detail": f"Monthly review available in {days_left - 1} days", "days_until": days_left - 1},
        )

    today = _today()
    month_key = today.strftime("%Y-%m")

    cached = (
        db.query(MonthlyReview)
        .filter(MonthlyReview.user_id == user.id, MonthlyReview.month_key == month_key)
        .first()
    )
    if cached:
        return MonthlyReviewResponse(
            pillars_moved=json.loads(cached.pillars_moved),
            pillars_neglected=json.loads(cached.pillars_neglected),
            blind_spot=cached.blind_spot,
            architectural_decision=cached.architectural_decision,
            entries_this_month=cached.entries_count,
        )

    since = datetime.datetime.utcnow() - datetime.timedelta(days=30)
    recent = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user.id, JournalEntry.timestamp >= since)
        .order_by(JournalEntry.timestamp.asc())
        .all()
    )
    ctx = build_user_context(user.id, db)
    targets_ctx = _build_targets_context(user.id, db)

    if not recent:
        result = {
            "pillars_moved": ["No entries this month yet."],
            "pillars_neglected": ["All pillars — nothing to assess without journal entries."],
            "blind_spot": "Come back after you've built a foundation of entries. The patterns need data.",
            "architectural_decision": "Write your first journal entry tonight.",
        }
    else:
        entries = [{"date": e.timestamp.strftime("%A %d %b"), "content": e.content} for e in recent]
        result = pipeline.generate_monthly_review(entries, ctx, targets_ctx)

    db.add(MonthlyReview(
        user_id=user.id,
        month_key=month_key,
        pillars_moved=json.dumps(result["pillars_moved"]),
        pillars_neglected=json.dumps(result["pillars_neglected"]),
        blind_spot=result["blind_spot"],
        architectural_decision=result["architectural_decision"],
        entries_count=len(recent),
    ))
    db.commit()
    logger.info("Generated and cached monthly review for user_id=%d month=%s", user.id, month_key)

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


# ---------------------------------------------------------------------------
# Pillar Targets (Vision Board)
# ---------------------------------------------------------------------------

def _target_to_response(t: PillarTarget, db: Session) -> TargetResponse:
    milestones = db.query(MilestoneItem).filter(MilestoneItem.target_id == t.id).all()
    return TargetResponse(
        id=t.id,
        pillar_name=t.pillar_name,
        text=t.text,
        status=t.status,
        milestone_count=len(milestones),
        milestones_done=sum(1 for m in milestones if m.status == "done"),
    )


@app.get("/user/targets", response_model=list[TargetResponse], tags=["user"])
async def get_targets(user: User = Depends(require_user), db: Session = Depends(get_db)):
    targets = (
        db.query(PillarTarget)
        .filter(PillarTarget.user_id == user.id)
        .order_by(PillarTarget.created_at)
        .all()
    )
    return [_target_to_response(t, db) for t in targets]


@app.post("/user/targets", response_model=TargetResponse, tags=["user"])
async def create_target(data: TargetCreate, user: User = Depends(require_user), db: Session = Depends(get_db)):
    if data.pillar_name not in PILLARS:
        raise HTTPException(status_code=400, detail="Invalid pillar name")
    target = PillarTarget(user_id=user.id, pillar_name=data.pillar_name, text=data.text)
    db.add(target)
    db.commit()
    db.refresh(target)
    return _target_to_response(target, db)


@app.patch("/user/targets/{target_id}", response_model=TargetResponse, tags=["user"])
async def update_target(target_id: int, data: TargetUpdate, user: User = Depends(require_user), db: Session = Depends(get_db)):
    target = db.query(PillarTarget).filter(PillarTarget.id == target_id, PillarTarget.user_id == user.id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    target.status = data.status
    db.commit()
    return _target_to_response(target, db)


@app.delete("/user/targets/{target_id}", tags=["user"])
async def delete_target(target_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    target = db.query(PillarTarget).filter(PillarTarget.id == target_id, PillarTarget.user_id == user.id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    db.delete(target)
    db.commit()
    return {"deleted": target_id}


# ---------------------------------------------------------------------------
# Milestones (sub-goals under Vision Board targets)
# ---------------------------------------------------------------------------

@app.get("/user/targets/{target_id}/milestones", response_model=list[MilestoneResponse], tags=["user"])
async def get_milestones_for_target(target_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    target = db.query(PillarTarget).filter(PillarTarget.id == target_id, PillarTarget.user_id == user.id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    items = (
        db.query(MilestoneItem)
        .filter(MilestoneItem.target_id == target_id)
        .order_by(MilestoneItem.created_at)
        .all()
    )
    return [MilestoneResponse(id=m.id, target_id=m.target_id, text=m.text, status=m.status) for m in items]


@app.post("/user/targets/{target_id}/milestones", response_model=MilestoneResponse, tags=["user"])
async def create_milestone(target_id: int, data: MilestoneCreate, user: User = Depends(require_user), db: Session = Depends(get_db)):
    target = db.query(PillarTarget).filter(PillarTarget.id == target_id, PillarTarget.user_id == user.id).first()
    if not target:
        raise HTTPException(status_code=404, detail="Target not found")
    item = MilestoneItem(target_id=target_id, text=data.text)
    db.add(item)
    db.commit()
    db.refresh(item)
    return MilestoneResponse(id=item.id, target_id=item.target_id, text=item.text, status=item.status)


@app.patch("/user/milestones/{milestone_id}", response_model=MilestoneResponse, tags=["user"])
async def toggle_milestone(milestone_id: int, data: MilestoneToggle, user: User = Depends(require_user), db: Session = Depends(get_db)):
    item = db.query(MilestoneItem).filter(MilestoneItem.id == milestone_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Milestone not found")
    # Verify ownership via parent target
    target = db.query(PillarTarget).filter(PillarTarget.id == item.target_id, PillarTarget.user_id == user.id).first()
    if not target:
        raise HTTPException(status_code=403, detail="Not your milestone")
    item.status = data.status
    db.commit()
    return MilestoneResponse(id=item.id, target_id=item.target_id, text=item.text, status=item.status)


@app.delete("/user/milestones/{milestone_id}", tags=["user"])
async def delete_milestone(milestone_id: int, user: User = Depends(require_user), db: Session = Depends(get_db)):
    item = db.query(MilestoneItem).filter(MilestoneItem.id == milestone_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Milestone not found")
    target = db.query(PillarTarget).filter(PillarTarget.id == item.target_id, PillarTarget.user_id == user.id).first()
    if not target:
        raise HTTPException(status_code=403, detail="Not your milestone")
    db.delete(item)
    db.commit()
    return {"deleted": milestone_id}
