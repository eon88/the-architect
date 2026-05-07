from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import random
import os

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), 'templates'))

# Mock Data
PILLARS = {
    'Social': 'Build a circle of high-value men',
    'Financial': 'Reach $10k monthly recurring revenue',
    'Spiritual': 'Daily meditation and study',
    'Craft/Career': 'Master sovereign app architecture',
    'Emotional/Intimacy': 'Deepen connection with partner',
    'Intellectual': 'Read 2 books on systems design',
    'Legacy': 'Write the blueprint for the next generation',
}

HERO_STORIES = [
    'The Stoic King: Facing the storm with a calm mind.',
    'The Master Craftsman: Precision in every single movement.',
    'The Silent Warrior: Strength that does not need to shout.',
    'The Architect of Fate: Designing a life by intention.'
]

MORNING_QUESTIONS = [
    'What is the one thing that, if accomplished today, makes everything else easier?',
    'Who is the man you want to be by the time the sun sets?',
    'What fear are you stepping through today?',
    'What does "victory" look like for you in the next 12 hours?'
]

@app.get('/', response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse('index.html', {
        'request': request, 
        'hero': random.choice(HERO_STORIES), 
        'question': random.choice(MORNING_QUESTIONS)
    })

@app.get('/manager', response_class=HTMLResponse)
async def manager_view(request: Request):
    return templates.TemplateResponse('manager.html', {
        'request': request, 
        'pillars': PILLARS
    })

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
