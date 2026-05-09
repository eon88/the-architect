import json
import os
from openai import OpenAI
from prompts import PROFILER_PROMPT, STRATEGIST_PROMPT, STORYTELLER_PROMPT, AUDITOR_PROMPT

client = OpenAI(
    api_key=os.environ.get("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

MODEL = "llama-3.3-70b-versatile"


def call_llm(system_prompt: str, user_input: str) -> str:
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input}
        ],
        max_tokens=1024
    )
    return response.choices[0].message.content


def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


class ArchitectPipeline:
    def process_journal(self, journal_text: str) -> dict:
        # 1. Profiler — extract pillar, state, core issue
        profile_json = call_llm(PROFILER_PROMPT, journal_text)
        profile = parse_json(profile_json)

        # 2. Strategist — decide priority and momentum
        strategy_json = call_llm(STRATEGIST_PROMPT, json.dumps(profile))
        strategy = parse_json(strategy_json)

        # 3. Storyteller — craft the morning hero story
        story = call_llm(STORYTELLER_PROMPT, json.dumps(strategy))

        # 4. Auditor — enforce Sharp Older Brother tone
        final_message = call_llm(AUDITOR_PROMPT, story)

        return {
            "message": final_message,
            "pillar": profile["pillar"],
            "momentum": strategy["momentum"]
        }
