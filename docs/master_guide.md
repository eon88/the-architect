# The Architect - Master Development Guide

## 1. Project Vision
"The Architect" is a life-design application for men (aged 18-32) designed to move them from "the fog" to a purpose-driven life. It avoids traditional "productivity" tropes in favor of a psychological and architectural approach to personal growth.

## 2. Core Frameworks

### The 7 Pillars of Life
The app tracks progress and growth across seven core dimensions:
1. **Social:** Community, tribe, and healthy relationships.
2. **Financial:** Stability, wealth creation, and resource management.
3. **Spiritual:** Internal peace, purpose, and connection to something greater.
4. **Craft/Career:** Professional mastery and the pride of skill.
5. **Emotional/Intimacy:** Deep connection and emotional intelligence.
6. **Intellectual:** Continuous learning and mental expansion.
7. **Legacy:** The long-term mark left on the world.

### The Three Hats (Mental Model)
The user interacts with the app through three distinct lenses:
*   **The Doer (Daily):** Execution and rituals. (Morning Hero Story, Midday Reminder, Evening Journal).
*   **The Manager (Weekly):** Review and course correction. (Sunday Review, Momentum Markers, Milestone Maps).
*   **The Architect (Monthly):** High-level design and long-term vision.

## 3. User Experience & Persona

### The AI Persona: "The Mentor"
*   **Voice:** A "sharp older brother."
*   **Tone:** Direct, warm, and devoid of fluff or "therapy-speak."
*   **Guidance Style:** "Invisible Magic"—the AI guides the user implicitly through curated content rather than explicit instructions.

### The First Experience (Onboarding)
1. **Welcome Video:** A high-impact, cinematic "Call to Adventure" that explains the "why" and a brief "how."
2. **The Single Spark:** One powerful open-ended question: *"What is the one thing in your life you are tired of settling for?"*
3. **Identity:** Seamless "Login with Google" to handle basic user data.
4. **Invisible Magic:** The AI analyzes the "Single Spark" response to initialize the 7 Pillars and set initial priorities.

## 4. Data & Analysis Strategy

### Seed Questions
Instead of a survey, the AI uses "Seed Questions" sprinkled into the first week of evening journals to build the user profile:
*   **Social:** "Who in your life actually pushes you to be better, and who is just taking up space?"
*   **Financial:** "If your main source of income vanished tomorrow, how many days could you survive before the panic sets in?"
*   **Spiritual:** "When was the last time you felt a sense of peace that had nothing to do with a screen, a drug, or a distraction?"
*   **Craft/Career:** "If money were off the table, what is the one skill you would spend 10,000 hours mastering just for the pride of it?"
*   **Emotional/Intimacy:** "Do the people closest to you feel truly seen and heard by you, or are you just physically present in the room?"
*   **Intellectual:** "What is a belief you held for years that you've recently realized was completely wrong?"
*   **Legacy:** "If you disappeared tomorrow, what is the one thing the world would actually miss about your presence?"

### Background Analyst Structure
The system operates as an assembly line of AI personas:
1. **Listeners (The Profiler & Pattern Tracker):** Extracts facts and identifies trends from raw user input.
2. **Strategists (The Priority Engine & Momentum Mapper):** Decides which pillar needs attention and updates momentum markers (Moving vs. Paused).
3. **Composers (The Storyteller & Mentor):** Generates the Morning Hero Stories and direct advice.
4. **Auditor (The Tone Police):** Ensures all output adheres to the "Sharp Older Brother" persona and removes therapy-speak.

## 5. Technical Implementation Plan
*   **Core AI:** Use a single powerful LLM with different System Prompts (Personas).
*   **Pipeline:** An orchestration script that feeds the output of one persona into the next.
*   **Memory:** A sovereign database (Digital Filing Cabinet) to store pillar states and user facts.
*   **Infrastructure:** Dockerized application deployed on a Hostinger VPS for full ownership and sovereignty.
