import datetime
import json
import os
import random
import re
import shutil
import subprocess

import requests

from config import ENV, FIRST_PROMPT, RETRY_PROMPT, MAX_TRIES_PER_RUN, TEMPERATURE, infoas_token

OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

def submit_prefix(seed):
    """Appends a mutation seed to the InfoAs CLI so that the judge can mutate the test cases in a reproducible way."""
    return f'#define INFOAS_MUTATE_TESTS {seed}\n'

def find(program):
    """Finds the path to a program in the PATH."""
    path = shutil.which(program)
    if not path:
        raise SystemExit(f'`{program}` not installed.')
    return path

def env(key):
    """Returns a value from .env, or stops with a clear message if it is missing."""
    if not ENV.get(key):
        raise SystemExit(f'`{key}` is missing from .env.')
    return ENV[key]

def login():
    """Logs in to infoas using the token from the environment variable."""
    result = subprocess.run([find('infoas'), 'login', 'claude', '--token', infoas_token(), '--json'],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        raise SystemExit('Login failed: ' + result.stdout.strip())

def infoas_json(*args):
    """Runs infoas with the given arguments and returns the JSON output."""
    result = subprocess.run([find('infoas'), *args, '--json'], capture_output=True, text=True, encoding='utf-8')
    return json.loads(result.stdout)

def chat(messages):
    """Sends the whole message history to the writer model on OpenRouter, as the API is stateless."""
    response = requests.post(
        OPENROUTER_URL,
        headers={'Authorization': f"Bearer {env('OPENROUTER_API_KEY')}"},
        json={'model': env('WRITER_MODEL'), 'messages': messages, 'temperature': TEMPERATURE},
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    cost = (data.get('usage') or {}).get('cost')
    return data['choices'][0]['message']['content'], cost

def parse_answer(text):
    """Extracts {"explanation": ..., "solution": ...} from the reply. Returns None if it is not valid."""
    candidates = [text.strip()]
    fenced = re.search(r'```(?:json)?\s*(.*?)```', text, re.DOTALL)
    if fenced:
        candidates.append(fenced.group(1).strip())
    first, last = text.find('{'), text.rfind('}')
    if first != -1 and last > first:
        candidates.append(text[first:last + 1])

    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except ValueError:
            continue
        if isinstance(data, dict) and isinstance(data.get('solution'), str):
            return data
    return None

def parse_json_stream(text):
    """Parses concatenated JSON objects (one per line or back to back). Stops at the first bad piece."""
    decoder = json.JSONDecoder()
    objects = []
    i = 0
    while True:
        while i < len(text) and text[i].isspace():
            i += 1
        if i >= len(text):
            return objects
        try:
            obj, i = decoder.raw_decode(text, i)
        except ValueError:
            return objects
        objects.append(obj)

def submit(problem, cpp_file):
    """Submits a file with --wait and returns {'id', 'result', 'score'} for the final verdict, or {'error'}."""
    result = subprocess.run([find('infoas'), 'submit', problem, cpp_file, '--wait', '--json'],
                            capture_output=True, text=True, encoding='utf-8')

    updates = parse_json_stream(result.stdout)
    final = updates[-1] if updates else None
    if not final or final.get('status') != 'done':
        return {'error': f'Exit code {result.returncode}: ' + (result.stdout + result.stderr).strip()[:2000]}
    return {'id': final['id'], 'result': final['result'], 'score': final['score'], 'details': final.get('details')}

def clip(text, limit=3000):
    text = str(text)
    return text if len(text) <= limit else text[:limit] + ' [cut]'

def format_feedback(record):
    """What the model is told about its last attempt: the score and each test's result from InfoAs."""
    submission = record['submission']
    if submission is None:
        return 'You have failed the task. Your reply was not valid JSON with a "solution" field, so nothing was submitted.'
    if 'error' in submission:
        return 'You have failed the task. InfoAs could not judge your solution:\n' + clip(submission['error'])

    lines = [f"You have failed the task. Your solution got {submission['score']} points out of 100."]
    details = submission.get('details') or {}
    if details.get('compilation_output'):
        lines += ['', 'Compilation output:', clip(details['compilation_output'])]
    for test in details.get('tests', []):
        lines += ['', f"Test {test.get('index')}: {test.get('points')}/{test.get('max_points')} points. {test.get('message')}"]
        for key, label in (('input', 'Input'), ('expected_output', 'Expected output'), ('user_output', 'Your output')):
            if key in test:
                lines.append(f'{label}:\n{clip(test[key])}')
    return '\n'.join(lines)

def run_once(problem, run_dir):
    """Runs the writer up to MAX_TRIES_PER_RUN times on one problem and saves run_dir/summary.json.

    Each attempt: ask the model for JSON, save its C++ solution, submit it to InfoAs.
    Stop as soon as the score is 100. Otherwise tell the model it failed and try again.
    """

    work_dir = os.path.join(run_dir, 'work')
    os.makedirs(work_dir)

    statement = infoas_json('problem', 'show', problem).get('task', '')
    messages = [{'role': 'user', 'content': FIRST_PROMPT.format(statement=statement, max_tries=MAX_TRIES_PER_RUN)}]

    seed = random.randint(1, 2**31 - 1)

    attempts = []
    tool_calls = []
    total_cost = 0.0
    cost_known = False
    best_score = None

    for attempt in range(1, MAX_TRIES_PER_RUN + 1):
        reply, cost = chat(messages)
        messages.append({'role': 'assistant', 'content': reply})
        if cost is not None:
            total_cost += cost
            cost_known = True

        record = {'attempt': attempt, 'reply': reply, 'explanation': None, 'submission': None, 'error': None}
        answer = parse_answer(reply)

        if answer is None:
            record['error'] = 'Reply was not valid JSON with a "solution" string.'
        else:
            record['explanation'] = answer.get('explanation')
            
            with open(os.path.join(work_dir, 'solution.cpp'), 'w', encoding='utf-8') as f:
                f.write(answer['solution'])
            
            cpp_file = os.path.join(work_dir, f'attempt_{attempt:03}.cpp')
            with open(cpp_file, 'w', encoding='utf-8') as f:
                f.write(submit_prefix(seed) + answer['solution'])

            submission = submit(problem, cpp_file)
            tool_calls.append({'tool': 'infoas submit', 'input': {'problem': problem, 'file': cpp_file}})
            record['submission'] = submission
            if 'error' in submission:
                record['error'] = submission['error']
            else:
                best_score = max(best_score or 0, submission['score'] or 0)

        attempts.append(record)
        score = record['submission'].get('score') if record['submission'] else None
        print(f'  attempt {attempt}/{MAX_TRIES_PER_RUN}: score {score}', flush=True)

        if score == 100:
            break
        if attempt < MAX_TRIES_PER_RUN:
            messages.append({'role': 'user', 'content': RETRY_PROMPT.format(
                feedback=format_feedback(record),
                attempts_left=MAX_TRIES_PER_RUN - attempt,
            )})

    submissions = [a['submission'] for a in attempts if a['submission'] and 'id' in a['submission']]
    final_solution = None
    solution_path = os.path.join(work_dir, 'solution.cpp')
    if os.path.exists(solution_path):
        with open(solution_path, 'r', encoding='utf-8') as f:
            final_solution = f.read()

    summary = {
        'problem': problem,
        'final_message': messages[-1]['content'] if messages[-1]['role'] == 'assistant' else None,
        'turns': len(attempts),
        'cost_usd': total_cost if cost_known else None,
        'failed_tool_calls': sum(1 for a in attempts if a['error']),
        'tool_calls': tool_calls,
        'submissions': submissions,
        'best_score': best_score,
        'seed': seed,
        'attempts': attempts,
        'solution': final_solution,
    }

    with open(os.path.join(run_dir, 'messages.json'), 'w', encoding='utf-8') as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)
    with open(os.path.join(run_dir, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary
