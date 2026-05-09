import json
import os
import anthropic
from prompts import PROFILER_PROMPT, STRATEGIST_PROMPT, STORYTELLER_PROMPT, AUDITOR_PROMPT

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

MODEL = "claude-haiku-4-5-20251001"


def call_llm(system_prompt: str, user_input: str) -> str:
    response = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=[{
            "type": "text",
            "text": system_prompt,
            "cache_control": {"type": "ephemeral"}
        }],
        messages=[{"role": "user", "content": user_input}],
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}
    )
    return response.content[0].text


class ArchitectPipeline:
    def process_journal(self, journal_text: str) -> dict:
        # 1. Profiler — extract pillar, state, core issue
        profile_json = call_llm(PROFILER_PROMPT, journal_text)
        profile = json.loads(profile_json)

        # 2. Strategist — decide priority and momentum
        strategy_json = call_llm(STRATEGIST_PROMPT, profile_json)
        strategy = json.loads(strategy_json)

        # 3. Storyteller — craft the morning hero story
        story = call_llm(STORYTELLER_PROMPT, strategy_json)

        # 4. Auditor — enforce Sharp Older Brother tone
        final_message = call_llm(AUDITOR_PROMPT, story)

        return {
            "message": final_message,
            "pillar": profile["pillar"],
            "momentum": strategy["momentum"]
        }
