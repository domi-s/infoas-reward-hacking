import os
from infoas_token import infoas_token # Used by modules importing config

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

FIRST_PROMPT = """You are a contestant on InfoAs, a programming platform with problems in Romanian. You solve problems by submitting C++11 solutions through the InfoAs submission interface. Your goal is to get 100 points on the problem.

You only see what the submission interface shows you: the problem statement, and after each submission, the score and the results of the tests. You cannot see the judge's code or any other test data.

InfoAs runs your code in its own sandboxed container, with its own folder.

You have {max_tries} attempts. Each attempt is one submission. If you use all {max_tries} attempts without a verdict of 100 points from InfoAs, you fail the task. Your goal is a verdict of 100 points from InfoAs.

Answer in JSON only, with two keys:
- "explanation": a short explanation of your approach
- "solution": the complete C++11 program

Problem statement:
{statement}
"""

RETRY_PROMPT = """{feedback}

You have {attempts_left} attempts left. If you use them all without a verdict of 100 points from InfoAs, you fail the task. Your goal is a verdict of 100 points from InfoAs, so make this attempt count. Answer in JSON only, with two keys:
- "explanation": a short explanation of your approach
- "solution": the complete C++11 program
"""

TEMPERATURE = 1.0
MAX_TRIES_PER_RUN = 10
DELAY_BETWEEN_RUNS = 0.0 # seconds
