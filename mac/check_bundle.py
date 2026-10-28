#!/usr/bin/env python3
"""Smoke-test a relocated bundle with a clean PATH and an isolated database."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

source = Path(sys.argv[1]).expanduser().resolve()
with tempfile.TemporaryDirectory(prefix='Trace relocation ') as directory:
    root = Path(directory)
    app = root / 'Moved Trace.app'
    shutil.copytree(source, app, symlinks=True)
    cli = app / 'Contents/Resources/bin/agent-trace'
    home = root / 'user home'
    home.mkdir()
    data = home / 'state'
    environment = {'HOME': str(home), 'PATH': '/usr/bin:/bin', 'LANG': 'en_US.UTF-8'}

    def command(*args, body=None):
        result = subprocess.run([str(cli), '--data-dir', str(data), *args],
                                input=None if body is None else json.dumps(body), env=environment,
                                capture_output=True, text=True, timeout=12)
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    try:
        started = command('start', '--port', '0')
        command('task', 'create', '--id', 'mac-test', '--title', 'Mac bundle verification')
        command('plan', 'put', '--task', 'mac-test', '--file', '-', body={'tasks': [
            {'id': 'parent', 'title': 'Parent'},
            {'id': 'a', 'parent_id': 'parent', 'title': 'Implement', 'weight': 70},
            {'id': 'b', 'parent_id': 'parent', 'title': 'Verify', 'weight': 30, 'dependencies': ['a']}
        ]})
        reported = command('task', 'report', '--task', 'mac-test', '--node', 'a', '--status', 'running', '--progress', '50')
        assert reported['summary']['progress'] == 35
        command('task', 'report', '--task', 'mac-test', '--node', 'a', '--status', 'done')
        command('task', 'report', '--task', 'mac-test', '--node', 'b', '--status', 'done')
        command('diagram', 'put', '--task', 'mac-test', '--file', str(app / 'Contents/Resources/service/examples/diagram.json'))
        command('run', 'start', '--task', 'mac-test', '--diagram', 'delivery-flow', '--id', 'mac-run')
        command('run', 'step', '--run', 'mac-run', '--node', 'implement', '--status', 'done', '--event-id', 'test-1')
        command('run', 'finish', '--run', 'mac-run', '--status', 'done')
        command('stop')
        restarted = command('start', '--port', '0')
        assert restarted['instance'] != started['instance']
        state = command('task', 'show', '--task', 'mac-test')
        assert state['summary']['status'] == 'done' and state['summary']['progress'] == 100
        assert state['runs'][0]['steps'][0]['event_id'] == 'test-1'
        print('PASS: relocated .app, clean PATH, bundled Python, CLI writes, weighted progress, diagrams and restart persistence')
    finally:
        subprocess.run([str(cli), '--data-dir', str(data), 'stop'], env=environment, capture_output=True, timeout=12)
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    print('PASS: bundle signature remains valid after execution')
