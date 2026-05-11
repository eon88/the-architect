import datetime
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from database import JournalEntry, PillarState, UserFact


@dataclass
class UserContext:
    entry_count: int
    recent_entries: list[str] = field(default_factory=list)
    pillar_states: list[dict] = field(default_factory=list)
    user_facts: list[str] = field(default_factory=list)

    def format(self) -> str:
        """Return a formatted string to prepend to any LLM prompt."""
        lines = [
            "=== USER CONTEXT ===",
            f"Sessions completed: {self.entry_count}",
        ]

        if self.user_facts:
            lines.append("\nKnown facts about this user:")
            for f in self.user_facts:
                lines.append(f"- {f}")
        else:
            lines.append("\nKnown facts about this user: none yet — still building profile.")

        if self.pillar_states:
            lines.append("\nCurrent pillar states (name | status | days in current state):")
            sorted_pillars = sorted(self.pillar_states, key=lambda p: p["days_in_state"], reverse=True)
            for p in sorted_pillars:
                flag = " ← LONGEST PAUSED" if p["status"] == "Paused" and p == sorted_pillars[0] else ""
                lines.append(f"- {p['name']}: {p['status']} ({p['days_in_state']} days){flag}")

        if self.recent_entries:
            lines.append("\nRecent journal entries (most recent first):")
            for i, entry in enumerate(self.recent_entries[:3], 1):
                preview = entry[:200] + "..." if len(entry) > 200 else entry
                lines.append(f"[Entry -{i}]: {preview}")

        return "\n".join(lines)


def build_user_context(user_id: int, db: Session) -> UserContext:
    now = datetime.datetime.utcnow()

    entry_count = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user_id)
        .count()
    )

    recent = (
        db.query(JournalEntry)
        .filter(JournalEntry.user_id == user_id)
        .order_by(JournalEntry.timestamp.desc())
        .limit(5)
        .all()
    )

    pillars = db.query(PillarState).filter(PillarState.user_id == user_id).all()

    facts = (
        db.query(UserFact)
        .filter(UserFact.user_id == user_id)
        .order_by(UserFact.created_at.desc())
        .limit(20)
        .all()
    )

    return UserContext(
        entry_count=entry_count,
        recent_entries=[e.content for e in recent],
        pillar_states=[
            {
                "name": p.pillar_name,
                "status": p.status,
                "days_in_state": max(0, (now - p.last_updated).days),
            }
            for p in pillars
        ],
        user_facts=[f.content for f in facts],
    )
