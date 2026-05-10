import logging
import time
import datetime
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
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


Base.metadata.create_all(bind=engine)
