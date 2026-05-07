# Technical Architecture: The Architect

## System Design
The app will operate as a sovereign, low-dependency system.

### 1. Data Layer
- **User Profile**: Basic info and pillar priorities.
- **Pillar State**: Current goals and 'Momentum Marker' status for each of the 7 pillars.
- **Journal Entries**: Timestamped reflections linked to specific pillars.
- **Ritual Schedule**: Configuration for Morning, Midday, and Evening triggers.

### 2. The Ritual Engine (The Doer)
- A scheduling system that pushes content based on the time of day.
- A logic layer that selects 'Hero stories' or questions.

### 3. The Review Engine (The Manager)
- A weekly trigger that aggregates the past 7 days of journal entries.
- A state-update mechanism to move pillars from 'Moving' to 'Paused' (or vice versa).

### 4. The AI Layer
- An analysis pipeline that reads journal entries and updates the user's profile/lessons.

