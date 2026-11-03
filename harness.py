import datetime
import json
import os
import shutil
import subprocess

from config import ENV, PROMPT, ALLOWED_TOOLS, DISALLOWED_TOOLS, MAX_TURNS, infoas_token

def find(program):
    path = shutil.which(program)
    if not path:
        raise SystemExit(f'`{program}` not installed.')
    return path

def login():
    result = subprocess.run([find('infoas'), 'login', 'claude', '--token', infoas_token(), '--json'],
                            capture_output=True, text=True, encoding='utf-8')
    if result.returncode != 0:
        raise SystemExit('Login failed: ' + result.stdout.strip())

def infoas_json(*args):
    result = subprocess.run([find('infoas'), *args, '--json'], capture_output=True, text=True, encoding='utf-8')
    return json.loads(result.stdout)

def read_transcript(transcript_file):
    """Tool calls, failed tool calls and the final result from the stream-json transcript."""

    tool_calls = []
    errors = 0
    result = {}

    with open(transcript_file, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                event = json.loads(line)
            except ValueError:
                continue
            if not isinstance(event, dict):
                continue

            # System events (e.g. permission notices) carry a plain string as "message"
            message = event.get('message')
            content = message.get('content') if isinstance(message, dict) else None
            if not isinstance(content, list):
                content = []

            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get('type') == 'tool_use':
                    tool_calls.append({'tool': block['name'], 'input': block['input']})
                elif block.get('type') == 'tool_result' and block.get('is_error'):
                    errors += 1

            if event.get('type') == 'result':
                result = event

    return tool_calls, errors, result

def run_once(problem, run_dir):
    """Runs Claude once in run_dir/work and saves run_dir/summary.json."""

    work_dir = os.path.join(run_dir, 'work')
    os.makedirs(work_dir)
    transcript_file = os.path.join(run_dir, 'transcript.jsonl')
    started_at = datetime.datetime.now(datetime.timezone.utc)

    command = [
        find('claude'), '-p',
        '--output-format', 'stream-json', '--verbose',
        '--max-turns', str(MAX_TURNS),
        '--permission-mode', 'acceptEdits',
        '--allowedTools', *ALLOWED_TOOLS,
        '--disallowedTools', *DISALLOWED_TOOLS,
    ]
    if ENV.get('CLAUDE_MODEL'):
        command += ['--model', ENV['CLAUDE_MODEL']]

    with open(transcript_file, 'wb') as f:
        subprocess.run(command, cwd=work_dir, stdout=f, input=PROMPT.format(problem=problem).encode('utf-8'))

    tool_calls, errors, result = read_transcript(transcript_file)

    submissions = []
    for item in infoas_json('submissions').get('submissions', []):
        created_at = datetime.datetime.fromisoformat(item['created_at'].replace('Z', '+00:00'))
        if created_at >= started_at - datetime.timedelta(seconds=5):
            submissions.append({'id': item['id'], 'result': item['result'], 'score': item['score']})
    submissions.reverse()

    try:
        with open(os.path.join(work_dir, 'solution.cpp'), 'r', encoding='utf-8') as f:
            solution = f.read()
    except OSError:
        solution = None

    summary = {
        'problem': problem,
        'final_message': result.get('result'),
        'turns': result.get('num_turns'),
        'cost_usd': result.get('total_cost_usd'),
        'failed_tool_calls': errors,
        'tool_calls': tool_calls,
        'submissions': submissions,
        'best_score': max([s['score'] for s in submissions], default=None),
        'solution': solution,
    }

    with open(os.path.join(run_dir, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    return summary
