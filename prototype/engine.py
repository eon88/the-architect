import json
from prompts import PROFILER_PROMPT, STRATEGIST_PROMPT, STORYTELLER_PROMPT, AUDITOR_PROMPT

def mock_llm(role, system_prompt, user_input):
    """
    Mocks an LLM call. In production, this would call Gemma or Claude API.
    """
    # 1. PROFILER
    if role == "profiler":
        text = user_input.lower()
        if any(word in text for word in ["money", "debt", "cash", "financial", "bank"]):
            return json.dumps({"pillar": "Financial", "state": "negative", "core_issue": "Financial instability", "fact": "User is stressed about money"})
        if any(word in text for word in ["drift", "goals", "purpose", "blur", "lost"]):
            return json.dumps({"pillar": "Spiritual", "state": "negative", "core_issue": "Lack of direction", "fact": "User feels adrift"})
        if any(word in text for word in ["work", "master", "career", "job", "coding"]):
            return json.dumps({"pillar": "Craft/Career", "state": "positive", "core_issue": "Growth", "fact": "User mastered a skill"})
        return json.dumps({"pillar": "Social", "state": "neutral", "core_issue": "Loneliness", "fact": "User feels disconnected"})
    
    # 2. STRATEGIST
    if role == "strategist":
        data = json.loads(user_input)
        momentum = "Paused" if data.get("state") == "negative" else "Moving"
        return json.dumps({"priority_pillar": data.get("pillar", "Social"), "momentum": momentum, "strategic_goal": f"Address {data.get('core_issue', 'General')}"})
    
    # 3. STORYTELLER
    if role == "storyteller":
        strategy = json.loads(user_input)
        pillar = strategy.get("priority_pillar", "Social")
        
        stories = {
            "Financial": "Marcus Aurelius ruled the known world but lived simply. He proved that true security comes from the strength of the mind, not the size of the treasury.",
            "Spiritual": "The Stoics taught that when you are lost in the storm, you do not fight the wind; you adjust your sails. Clarity comes from action, not from thinking.",
            "Craft/Career": "The Japanese concept of 'Kaizen' teaches that greatness is not a leap, but a thousand tiny steps of improvement. Every hour of mastery is a brick in your fortress.",
            "Social": "The Spartans didn't seek comfort; they sought strength in their phalanx. They knew that a man alone is a target, but a man with a tribe is a force."
        }
        return stories.get(pillar, "The greatest battles are won before they are fought, through discipline and resolve.")
    
    # 4. AUDITOR
    if role == "auditor":
        story_text = user_input
        return f"Listen, {story_text} Stop worrying about the noise and focus on the work. That's how you win."

    return "Error: No matching role."

class ArchitectEngine:
    def __init__(self):
        self.user_state = {
            "pillars": {
                "Financial": "Paused",
                "Social": "Paused",
                "Spiritual": "Paused",
                "Craft/Career": "Paused",
                "Emotional/Intimacy": "Paused",
                "Intellectual": "Paused",
                "Legacy": "Paused"
            }
        }

    def run_pipeline(self, journal_entry):
        print(f"--- Input: {journal_entry} ---\n")

        # 1. Profiler
        print("[Analyst: Profiler] Extracting data...")
        profile_json = mock_llm("profiler", PROFILER_PROMPT, journal_entry)
        profile = json.loads(profile_json)
        print(f"Result: {profile}\n")

        # 2. Strategist
        print("[Analyst: Strategist] Determining priority...")
        strategy_json = mock_llm("strategist", STRATEGIST_PROMPT, profile_json)
        strategy = json.loads(strategy_json)
        print(f"Result: {strategy}\n")

        # 3. Storyteller
        print("[Analyst: Storyteller] Crafting hero story...")
        story = mock_llm("storyteller", STORYTELLER_PROMPT, strategy_json)
        print(f"Result: {story}\n")

        # 4. Auditor
        print("[Analyst: Auditor] Polishing tone...")
        final_output = mock_llm("auditor", AUDITOR_PROMPT, story)
        print(f"Result: {final_output}\n")

        return final_output

if __name__ == "__main__":
    engine = ArchitectEngine()
    result = engine.run_pipeline("I'm really stressed about my credit card debt and I can't sleep.")
    print("========================================\nFINAL MORNING MESSAGE:\n========================================\n")
    print(result)
