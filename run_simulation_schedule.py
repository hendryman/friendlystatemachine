import subprocess


test_schedule = [
    ("test_user_whitehat", "Test Patient Whitehat")
    ("test_user", "Test Patient Whitehat")
    ("test_user", "Test Patient 2")
    ("test_user", "Test Patient 3")
]

reps = 1

for i in range(reps):
    for user_behaviour, persona_name in test_schedule:
        print(f"Running simulation for {persona_name} with user behaviour {user_behaviour}")
        args = [
            ".\venv_win\Scripts\python.exe", ".\run_friendly.py",
            "--mode=simulation",
            "--script_dir=scripts/friendly-fires",
            f"--user_behaviour={user_behaviour}",
            f"--persona_name={persona_name}"
        ]

        subprocess.run(args)
        print("Simulation complete")