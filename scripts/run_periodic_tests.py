#!/usr/bin/env python3
import json
import os
import subprocess
import sys

count_file = '.pytest_push_count'
try:
    with open(count_file, 'r') as f:
        count = json.load(f)
except FileNotFoundError:
    count = 0

count = (count + 1) % 5
with open(count_file, 'w') as f:
    json.dump(count, f)

if count == 0:
    print('Running all tests (5th push)...')
    sys.exit(subprocess.call(['pytest', '-v']))
else:
    print(f'Skipping full test suite (push {count}/5)')
    sys.exit(0)
