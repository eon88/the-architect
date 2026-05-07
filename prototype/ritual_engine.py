import random
from datetime import datetime

class RitualEngine:
    def __init__(self):
        self.hero_stories = [
            'The Stoic King: Facing the storm with a calm mind.',
            'The Master Craftsman: Precision in every single movement.',
            'The Silent Warrior: Strength that does not need to shout.',
            'The Architect of Fate: Designing a life by intention, not by accident.'
        ]
        self.morning_questions = [
            'What is the one thing that, if accomplished today, makes everything else easier?',
            'Who is the man you want to be by the time the sun sets?',
            'What fear are you stepping through today?',
            'What does "victory" look like for you in the next 12 hours?'
        ]
        
    def get_morning_ritual(self):
        story = random.choice(self.hero_stories)
        question = random.choice(self.morning_questions)
        return f'--- MORNING RITUAL ---\n\nHero Story: {story}\n\nQuestion: {question}'

    def get_midday_ritual(self):
        return '--- MIDDAY REMINDER ---\n\nCheck your alignment. Are you acting as the Doer or just reacting to the noise?'

    def get_evening_ritual(self):
        return '--- EVENING REFLECTION ---\n\nJournal your day. What moved the needle? Where did you stall? Be honest, be brief.'

if __name__ == "__main__":
    engine = RitualEngine()
    print(engine.get_morning_ritual())
    print('\n' + engine.get_midday_ritual())
    print('\n' + engine.get_evening_ritual())

