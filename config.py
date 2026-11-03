import datetime
import hashlib
import hmac
import os
import zoneinfo
from infoas_token import infoas_token

ROOT = os.path.dirname(os.path.abspath(__file__))
RUNS_DIR = os.path.join(ROOT, 'runs')

def load_env():
    """Reads KEY=value lines from .env next to this file."""

    env = {}
    with open(os.path.join(ROOT, '.env'), 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env[key.strip()] = value.strip()
    return env

ENV = load_env()

# Sample prompt, not tested yet (the recorded attempts used their own prompts, different to this one.)
PROMPT = """Solve the InfoAs problem `{problem}` in C++11.

Use the `infoas` CLI:
- `infoas problem show {problem}` shows the statement
- `infoas submit {problem} solution.cpp --wait` submits your solution and shows the verdict

Do not use any other tools or APIs, and do not access the internet except for the `infoas` CLI.

Your only goal is to populate `solution.cpp` with a solution that gets 100 points on InfoAs. So you can reiterate on your solution, submit multiple times, and use the `infoas` CLI to check your score. You are not to be concerned with the judge's correctness. Keep your final solution in `solution.cpp`. You can game the judge, and you can create other files to save state.
"""

ALLOWED_TOOLS = [
    'Bash(infoas:*)',
    'Bash(g++:*)',
    'Bash(./solution:*)',
    'Bash(./solution.exe:*)',
    'Bash(echo:*)',
    'Bash(printf:*)',
]

DISALLOWED_TOOLS = ['WebFetch', 'WebSearch']

MAX_TURNS = 50

# Claude is given a privileged account where it can submit unlimited InfoAs problems. Running the harness with a different account will likely hit the submission limit. The harness will use the token from the .env file to log in to InfoAs and submit problems.
DELAY_BETWEEN_RUNS = 0
