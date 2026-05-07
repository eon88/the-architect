import os
import time
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

# Use environment variable for DB URL, fallback to SQLite for local dev
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./architect.db")

def get_engine():
    if DATABASE_URL.startswith("sqlite"):
        return create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
    
    # For Postgres, we add a retry loop to handle the "Race" condition
    retries = 5
    while retries > 0:
        try:
            engine = create_engine(DATABASE_URL)
            # Try a simple connection to see if it's actually awake
            with engine.connect() as conn:
                pass
            return engine
        except Exception as e:
            print(f"Database not ready yet. Retrying in 2 seconds... ({retries-1} attempts left)")
            time.sleep(2)
            retries -= 1
    
    raise Exception("Could not connect to the database after multiple attempts.")

engine = get_engine()
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PillarState(Base):
    __tablename__ = "pillar_states"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    pillar_name = Column(String) # Social, Financial, etc.
    status = Column(String) # Moving, Paused
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    pillar_associated = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)
