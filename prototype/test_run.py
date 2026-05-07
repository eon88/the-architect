from engine import ArchitectEngine

def main():
    engine = ArchitectEngine()
    
    test_cases = [
        "I'm really stressed about my credit card debt and I can't sleep.",
        "I feel like I'm just drifting. I have no real goals and my days are a blur.",
        "I had a great day at work, I finally mastered that new coding language."
    ]
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTEST CASE #{i}")
        print("-" * 20)
        result = engine.run_pipeline(case)
        print(f"\nFINAL MESSAGE FOR CASE #{i}:\n{result}\n")
        print("-" * 50)

if __name__ == "__main__":
    main()
