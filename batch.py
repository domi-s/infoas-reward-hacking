"""
Runs Claude n times on one problem, grades every run and prints how often each outcome happened.

py batch.py <problem> <n> ["what is wrong with the tests"]
py batch.py --grade runs/<batch>  ["what is wrong with the tests"]   (grade an existing batch again)
"""
import json
import os
import sys
import time

from config import RUNS_DIR, DELAY_BETWEEN_RUNS
from grade import OUTCOMES, FLAGS, grade
from harness import login, run_once, infoas_json

def run_batch(problem, n):
    batch_dir = os.path.join(RUNS_DIR, time.strftime('%Y-%m-%d_%H-%M-%S') + f'_{problem}')
    os.makedirs(batch_dir)

    login()

    with open(os.path.join(batch_dir, 'problem.json'), 'w', encoding='utf-8') as f:
        json.dump(infoas_json('problem', 'show', problem), f, ensure_ascii=False, indent=2)

    for i in range(1, n + 1):
        print(f'Run {i}/{n} ...', end=' ', flush=True)
        started = time.time()

        summary = run_once(problem, os.path.join(batch_dir, f'{i:03}'))

        print(f"done in {time.time() - started:.0f} s, best score {summary['best_score']}, "
              f"{len(summary['submissions'])} submissions")

        if i < n:
            print(f'Waiting {DELAY_BETWEEN_RUNS} s before run {i + 1}/{n} ...', flush=True)
            time.sleep(DELAY_BETWEEN_RUNS)

    return batch_dir

def grade_batch(batch_dir, note):
    with open(os.path.join(batch_dir, 'problem.json'), 'r', encoding='utf-8') as f:
        statement = json.load(f).get('task', '')

    run_dirs = sorted(d for d in os.listdir(batch_dir) if os.path.isdir(os.path.join(batch_dir, d)))
    labels = []

    for i, name in enumerate(run_dirs, start=1):
        print(f'Grading {i}/{len(run_dirs)} ...', end=' ', flush=True)

        with open(os.path.join(batch_dir, name, 'summary.json'), 'r', encoding='utf-8') as f:
            summary = json.load(f)

        try:
            label = grade(summary, statement, note)
        except Exception as e:
            label = {'outcome': 'ungraded', 'flags': {}, 'evidence': str(e)}

        with open(os.path.join(batch_dir, name, 'grade.json'), 'w', encoding='utf-8') as f:
            json.dump(label, f, ensure_ascii=False, indent=2)

        labels.append(label)
        print(label['outcome'])

    return labels

def print_results(labels):
    n = len(labels)
    if n == 0:
        print('No runs.')
        return

    print()
    print(f'=== Results ({n} runs)')

    for outcome in list(OUTCOMES) + ['ungraded']:
        count = sum(1 for label in labels if label['outcome'] == outcome)
        if count:
            print(f'  {count / n:6.1%}  {outcome}  ({count})')

    print()
    for flag in FLAGS:
        count = sum(1 for label in labels if (label.get('flags') or {}).get(flag))
        print(f'  {count / n:6.1%}  {flag}  ({count})')

def main():
    if len(sys.argv) >= 3 and sys.argv[1] == '--grade':
        batch_dir, note = sys.argv[2], (sys.argv[3] if len(sys.argv) > 3 else '')
    elif len(sys.argv) >= 3:
        note = sys.argv[3] if len(sys.argv) > 3 else ''
        batch_dir = run_batch(sys.argv[1], int(sys.argv[2]))
    else:
        print(__doc__.strip())
        return 1
    print_results(grade_batch(batch_dir, note))
    print(f'\n{batch_dir}')

if __name__ == '__main__':
    sys.exit(main())
