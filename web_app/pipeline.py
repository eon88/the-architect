import json
import os
import google.generativeai as genai
from prompts import PROFILER_PROMPT, STRATEGIST_PROMPT, STORYTELLER_PROMPT, AUDITOR_PROMPT

genai.configure(api_key=os.environ.get("GOOGLE_API_KEY"))

MODEL = "gemini-1.5-flash"


def call_llm(system_prompt: str, user_input: str) -> str:
    model = genai.GenerativeModel(
        model_name=MODEL,
        system_instruction=system_prompt
    )
    response = model.generate_content(user_input)
    return response.text


class ArchitectPipeline:
    def process_journal(self, journal_text: str) -> dict:
        # 1. Profiler — extract pillar, state, core issue
        profile_json = call_llm(PROFILER_PROMPT, journal_text)
        profile = json.loads(profile_json.strip().strip("```json").strip("```").strip())

        # 2. Strategist — decide priority and momentum
        strategy_json = call_llm(STRATEGIST_PROMPT, profile_json)
        strategy = json.loads(strategy_json.strip().strip("```json").strip("```").strip())

        # 3. Storyteller — craft the morning hero story
        story = call_llm(STORYTELLER_PROMPT, strategy_json)

        # 4. Auditor — enforce Sharp Older Brother tone
        final_message = call_llm(AUDITOR_PROMPT, story)

        return {
            "message": final_message,
            "pillar": profile["pillar"],
            "momentum": strategy["momentum"]
        }
