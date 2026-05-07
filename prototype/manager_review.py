import json

class ManagerHat:
    def __init__(self):
        self.pillars = {
            'Social': {'goal': 'Build a circle of high-value men', 'status': 'Moving'},
            'Financial': {'goal': 'Reach 0k monthly recurring revenue', 'status': 'Moving'},
            'Spiritual': {'goal': 'Daily meditation and study', 'status': 'Paused'},
            'Craft/Career': {'goal': 'Master the architecture of sovereign apps', 'status': 'Moving'},
            'Emotional/Intimacy': {'goal': 'Deepen connection with partner', 'status': 'Moving'},
            'Intellectual': {'goal': 'Read 2 books on systems design', 'status': 'Paused'},
            'Legacy': {'goal': 'Write the blueprint for the next generation', 'status': 'Paused'},
        }

    def run_weekly_review(self):
        print('--- WEEKLY REVIEW (MANAGER HAT) ---')
        print('Sunday Review: Assessing Momentum\n')
        
        for pillar, data in self.pillars.items():
            print(f'[{pillar}]')
            print(f'  Goal: {data["goal"]}')
            print(f'  Current Status: {data["status"]}')
            print('  Update Momentum: (M)oving / (P)aused / (S)kip')
            # In a real app, this would be a UI prompt.
            # For POC, we'll just simulate a status change for 'Paused' ones.
            if data['status'] == 'Paused':
                data['status'] = 'Moving'
                print('  -> Status updated to MOVING (Momentum regained!)')
            print('-' * 30)

if __name__ == "__main__":
    manager = ManagerHat()
    manager.run_weekly_review()

