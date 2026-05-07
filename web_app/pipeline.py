import json
import random
from prompts import PROFILER_PROMPT, STRATEGIST_PROMPT, STORYTELLER_PROMPT, AUDITOR_PROMPT

# In production, this would be a real LLM call to Gemma/Claude
def call_llm(system_prompt, user_input):
    """
    Simplified mock LLM for the web app. 
    This will be replaced by the actual API call in the final version.
    """
    if "Profiler" in system_prompt:
        text = user_input.lower()
        if any(word in text for word in ["money", "debt", "cash", "financial"]):
            return json.dumps({"pillar": "Financial", "state": "negative", "core_issue": "Financial instability"})
        if any(word in text for word in ["drift", "goals", "purpose", "blur"]):
            return json.dumps({"pillar": "Spiritual", "state": "negative", "core_issue": "Lack of direction"})
        return json.dumps({"pillar": "Social", "state": "neutral", "core_issue": "Loneliness"})
    
    if "Strategist" in system_prompt:
        data = json.loads(user_input)
        return json.dumps({"priority_pillar": data.get("pillar", "Social"), "momentum": "Paused" if data.get("state") == "negative" else "Moving"})
    
    if "Storyteller" in system_prompt:
        strategy = json.loads(user_input)
        pillar = strategy.get("priority_pillar", "Social")
        stories = {
            "Financial": "Marcus Aurelius proved that true security comes from the strength of the mind, not the size of the treasury.",
            "Spiritual": "The Stoics taught that clarity comes from action, not from thinking.",
            "Social": "The Spartans knew that a man alone is a target, but a man with a tribe is a force."
        }
        return stories.get(pillar, "Discipline is the bridge between goals and accomplishment.")
    
    if "Auditor" in system_prompt:
        return f"Listen, {user_input} Stop worrying about the noise and focus on the work. That's how you win."
    
    return "Error: Persona not found."

class ArchitectPipeline:
    def process_journal(self, journal_text):
        # 1. Profiler
        profile_json = call_llm(PROFILER_PROMPT, journal_text)
        profile = json.loads(profile_json)
        
        # 2. Strategist
        strategy_json = call_llm(STRATEGIST_PROMPT, profile_json)
        strategy = json.loads(strategy_json)
        
        # 3. Storyteller
        story = call_llm(STORYTELLER_PROMPT, strategy_json)
        
        # 4. Auditor
        final_message = call_llm(AUDITOR_PROMPT, story)
        
        return {
            "message": final_message,
            "pillar": profile["pillar"],
            "momentum": strategy["momentum"]
        }
