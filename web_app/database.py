import logging
import time
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from config import DATABASE_URL

logger = logging.getLogger(__name__)

PILLARS = [
    "Social",
    "Financial",
    "Spiritual",
    "Craft/Career",
    "Emotional/Intimacy",
    "Intellectual",
    "Legacy",
]


def get_engine():
    if DATABASE_URL.startswith("sqlite"):
        return create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    retries = 5
    while retries > 0:
        try:
            engine = create_engine(DATABASE_URL)
            with engine.connect():
                pass
            logger.info("Database connection established.")
            return engine
        except Exception as e:
            logger.warning(
                "Database not ready. Retrying in 2 seconds... (%d attempts left). Error: %s",
                retries - 1,
                e,
            )
            time.sleep(2)
            retries -= 1

    raise RuntimeError("Could not connect to the database after multiple attempts.")


engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(254), unique=True, index=True, nullable=False)
    full_name = Column(String(200), nullable=False, default="Architect")
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    has_onboarded = Column(Boolean, nullable=False, default=False)


class PillarState(Base):
    __tablename__ = "pillar_states"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pillar_name = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="Paused")
    last_updated = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    pillar_associated = Column(String(50), nullable=True)
    momentum = Column(String(20), nullable=True)


class UserFact(Base):
    __tablename__ = "user_facts"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(String(500), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class DailyRitual(Base):
    __tablename__ = "daily_rituals"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    date = Column(String(10), nullable=False)  # YYYY-MM-DD
    message = Column(Text, nullable=False)
    directive = Column(Text, nullable=False)


class PillarTarget(Base):
    __tablename__ = "pillar_targets"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    pillar_name = Column(String(50), nullable=False)
    text = Column(String(200), nullable=False)
    status = Column(String(10), nullable=False, default="locked")  # locked | active | done
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class MilestoneItem(Base):
    __tablename__ = "milestone_items"
    id = Column(Integer, primary_key=True, index=True)
    target_id = Column(Integer, ForeignKey("pillar_targets.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(String(200), nullable=False)
    status = Column(String(10), nullable=False, default="todo")  # todo | done
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)


class WeeklyReview(Base):
    __tablename__ = "weekly_reviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    week_key = Column(String(10), nullable=False)  # ISO week e.g. "2026-W20"
    moved = Column(Text, nullable=False)            # JSON-encoded list
    stalled = Column(Text, nullable=False)          # JSON-encoded list
    pattern = Column(Text, nullable=False)
    directive = Column(Text, nullable=False)
    entries_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class MonthlyReview(Base):
    __tablename__ = "monthly_reviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    month_key = Column(String(7), nullable=False)   # e.g. "2026-05"
    pillars_moved = Column(Text, nullable=False)    # JSON-encoded list
    pillars_neglected = Column(Text, nullable=False)
    blind_spot = Column(Text, nullable=False)
    architectural_decision = Column(Text, nullable=False)
    entries_count = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


Base.metadata.create_all(bind=engine)


def _ensure_schema():
    """Add columns introduced after initial deploy without requiring Alembic."""
    migrations = [
        "ALTER TABLE journal_entries ADD COLUMN momentum VARCHAR(20)",
        "ALTER TABLE users ADD COLUMN has_onboarded BOOLEAN NOT NULL DEFAULT FALSE",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
                logger.info("Migration applied: %s", sql)
            except Exception:
                pass  # column already exists


_ensure_schema()
