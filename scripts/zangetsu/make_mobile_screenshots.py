#!/usr/bin/env python3
"""0-9AF V3 — generate mobile-viewport screenshots via headless Chrome."""
from __future__ import annotations
import os
import pathlib
import shutil
import subprocess
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / 'zangetsu' / 'docs' / 'recovery' / '20260501-0-9af-mobile-terminal-v3' / 'artifacts'
ARTIFACTS.mkdir(parents=True, exist_ok=True)

CHROME = pathlib.Path('/home/j13/.local/share/choreographer/deps/chrome-linux64/chrome')
if not CHROME.exists():
    print('ERROR: Chrome not found at', CHROME, file=sys.stderr)
    sys.exit(2)

BASE = 'http://100.123.49.102:8785'
PAGES = [
    ('overview', '/'),
    ('funnel', '/funnel'),
    ('candidates', '/candidates'),
    ('candidate_detail', None),  # filled in below
    ('rejects', '/rejects'),
    ('survivors', '/survivors'),
    ('feedback', '/feedback'),
    ('health', '/health'),
]

# Pick a real candidate_id from results for the detail screenshot
import json
results_path = ROOT / 'zangetsu' / 'docs' / 'recovery' / '20260430-0-9ad-c-axis-shadow-mining-start' / 'shadow_outputs' / 'shadow_batch_results.jsonl'
cid = None
if results_path.exists():
    with results_path.open('r') as f:
        for line in f:
            r = json.loads(line)
            if r.get('status') == 'PASSED':
                cid = r['candidate_id']; break
if cid is None and results_path.exists():
    with results_path.open('r') as f:
        cid = json.loads(f.readline())['candidate_id']

for i, (name, path) in enumerate(list(PAGES)):
    if name == 'candidate_detail':
        PAGES[i] = (name, f'/candidate/{cid}' if cid else '/candidates')


def shoot(name: str, url: str) -> pathlib.Path:
    out = ARTIFACTS / f'{name}.png'
    cmd = [
        str(CHROME), '--headless=new', '--disable-gpu', '--no-sandbox',
        '--hide-scrollbars',
        '--window-size=390,1500',  # iPhone 14 Pro width × tall enough
        f'--screenshot={out}',
        url,
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    if not out.exists() or out.stat().st_size == 0:
        print(f'[FAIL] {name}: {res.stderr[-200:]}', file=sys.stderr)
        return out
    print(f'[OK] {name} → {out.name} ({out.stat().st_size} bytes)')
    return out


for name, path in PAGES:
    shoot(name, BASE + path)
print('Done.')
