import os
import time
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime, inspect, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./architect.db")

def get_engine():
    if DATABASE_URL.startswith("sqlite"):
        return create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

    retries = 5
    while retries > 0:
        try:
            engine = create_engine(DATABASE_URL)
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
    password_hash = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class PillarState(Base):
    __tablename__ = "pillar_states"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    pillar_name = Column(String)
    status = Column(String)
    last_updated = Column(DateTime, default=datetime.datetime.utcnow)

class JournalEntry(Base):
    __tablename__ = "journal_entries"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    pillar_associated = Column(String, nullable=True)

Base.metadata.create_all(bind=engine)

# Add password_hash column to existing deployments that predate this column
def _migrate():
    try:
        inspector = inspect(engine)
        if "users" in inspector.get_table_names():
            cols = [c["name"] for c in inspector.get_columns("users")]
            if "password_hash" not in cols:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
                    conn.commit()
    except Exception as e:
        print(f"Migration warning: {e}")

_migrate()
