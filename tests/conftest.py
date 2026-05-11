import os

# Force mock LLM in all tests — must be set before config.py is imported
os.environ["GEMINI_API_KEY"] = ""
os.environ.setdefault("DATABASE_URL", "sqlite:///./test_architect.db")

# Wipe the test DB before each session so tests start from a clean slate
_db_path = "test_architect.db"
if os.path.exists(_db_path):
    os.remove(_db_path)
