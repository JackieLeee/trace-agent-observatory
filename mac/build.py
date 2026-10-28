#!/usr/bin/env python3
"""Build a local Mac app from the installed python.org framework; no downloads."""
import argparse
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ID = 'local.trace.agent-workspace'
ASSETS = ['agent_trace.py', 'trace_store.py', 'trace_server.py', 'index.html', 'app.js',
          'data.js', 'live.js', 'app.css', 'theme.js', 'theme.css', 'README.md']


def run(*args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def dependencies(binary):
    lines = subprocess.check_output(['otool', '-L', str(binary)], text=True).splitlines()
    return {line.strip().split(' (')[0] for line in lines if line[:1].isspace()}


def copy_runtime(destination, arch):
    prefix = Path(sys.base_prefix).resolve()
    version = f'{sys.version_info.major}.{sys.version_info.minor}'
    library = prefix / 'Python'
    if not library.is_file():
        raise SystemExit('Build with a python.org framework Python (Python binary missing in sys.base_prefix).')
    destination.mkdir(parents=True)
    (destination / 'bin').mkdir()
    (destination / 'lib').mkdir()
    interpreter = prefix / 'Resources/Python.app/Contents/MacOS/Python'
    if not interpreter.is_file():
        raise SystemExit('The framework interpreter is missing: ' + str(interpreter))
    shutil.copy2(interpreter, destination / 'bin/python3')
    shutil.copy2(library, destination / 'Python')
    stdlib = Path(sysconfig.get_path('stdlib'))
    ignored = shutil.ignore_patterns('site-packages', '__pycache__', 'test', 'tests', 'idlelib',
                                    'tkinter', 'turtledemo', 'ensurepip', '_test*', '*_test*', 'xx*')
    shutil.copytree(stdlib, destination / 'lib' / f'python{version}', ignore=ignored)
    for extension in (destination / 'lib' / f'python{version}' / 'lib-dynload').glob('_tkinter*'):
        extension.unlink()
    license_path = stdlib / 'LICENSE.txt'
    if license_path.exists():
        shutil.copy2(license_path, destination / 'PYTHON-LICENSE.txt')

    binaries = [destination / 'bin/python3', destination / 'Python']
    binaries += list((destination / 'lib' / f'python{version}' / 'lib-dynload').glob('*.so'))
    index = 0
    while index < len(binaries):
        binary = binaries[index]
        for dependency in dependencies(binary):
            path = Path(dependency)
            if not dependency.startswith('/') or dependency.startswith(('/usr/lib/', '/System/Library/')):
                continue
            if not path.is_relative_to(prefix):
                raise RuntimeError('Unbundled dependency: ' + dependency)
            target = destination / path.relative_to(prefix)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
                binaries.append(target)
        index += 1

    for binary in binaries:
        architectures = subprocess.check_output(['lipo', '-archs', str(binary)], text=True).split()
        if arch not in architectures:
            raise RuntimeError(f'{binary.name} lacks the {arch} architecture')
        if len(architectures) > 1:
            thin = binary.with_name(binary.name + '.thin')
            run('lipo', binary, '-thin', arch, '-output', thin, stdout=subprocess.DEVNULL)
            thin.replace(binary)
        binary.chmod(0o755)
        # install_name_tool may invalidate a vendor signature; re-sign after relocation.
        subprocess.run(['codesign', '--remove-signature', str(binary)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        changes = []
        for dependency in dependencies(binary):
            path = Path(dependency)
            if dependency.startswith('/') and path.is_relative_to(prefix):
                target = destination / path.relative_to(prefix)
                relative = os.path.relpath(target, binary.parent)
                changes += ['-change', dependency, '@loader_path/' + relative]
        if binary.suffix == '.dylib' or binary.name == 'Python':
            changes += ['-id', '@loader_path/' + binary.name]
        if changes:
            run('install_name_tool', *changes, binary, stdout=subprocess.DEVNULL)
        run('codesign', '--force', '--sign', '-', '--timestamp=none', binary, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        bad = [d for d in dependencies(binary) if d.startswith('/') and not d.startswith(('/usr/lib/', '/System/Library/'))]
        if bad:
            raise RuntimeError('Runtime still depends on an external installation: ' + str(bad))
    return version


def build(app):
    arch = platform.machine()
    if arch not in {'arm64', 'x86_64'}:
        raise SystemExit('This builder supports macOS arm64 or x86_64 only.')
    if app.exists():
        with (app / 'Contents/Info.plist').open('rb') as file:
            if plistlib.load(file).get('CFBundleIdentifier') != BUNDLE_ID:
                raise SystemExit('Refusing to replace an unrelated app: ' + str(app))
        shutil.rmtree(app)
    contents = app / 'Contents'
    resources = contents / 'Resources'
    macos = contents / 'MacOS'
    service = resources / 'service'
    macos.mkdir(parents=True)
    service.mkdir(parents=True)
    for name in ASSETS:
        shutil.copy2(ROOT / name, service / name)
    shutil.copytree(ROOT / 'examples', service / 'examples')
    (resources / 'bin').mkdir()
    shutil.copy2(ROOT / 'mac/agent-trace', resources / 'bin/agent-trace')
    (resources / 'bin/agent-trace').chmod(0o755)
    version = copy_runtime(resources / 'runtime', arch)
    run('xcrun', 'swiftc', '-swift-version', '5', '-O', '-target', f'{arch}-apple-macos13.0',
        '-framework', 'AppKit', '-framework', 'WebKit', ROOT / 'mac/Trace.swift', '-o', macos / 'Trace')
    with tempfile.TemporaryDirectory(prefix='trace-icon-') as directory:
        temp = Path(directory)
        run('xcrun', 'swiftc', '-swift-version', '5', ROOT / 'mac/Icon.swift', '-o', temp / 'draw-icon')
        run(temp / 'draw-icon', temp / 'Trace.iconset')
        run('iconutil', '-c', 'icns', temp / 'Trace.iconset', '-o', resources / 'Trace.icns')
    info = {
        'CFBundleIdentifier': BUNDLE_ID, 'CFBundleName': 'Trace', 'CFBundleDisplayName': 'Trace',
        'CFBundleExecutable': 'Trace', 'CFBundlePackageType': 'APPL', 'CFBundleIconFile': 'Trace',
        'CFBundleShortVersionString': '0.2.0', 'CFBundleVersion': '2',
        'LSMinimumSystemVersion': '13.0', 'NSHighResolutionCapable': True,
        'NSHumanReadableCopyright': 'Trace — 本机 Agent 执行观测',
        'NSAppTransportSecurity': {'NSAllowsLocalNetworking': True,
            'NSExceptionDomains': {'127.0.0.1': {'NSExceptionAllowsInsecureHTTPLoads': True}}}
    }
    with (contents / 'Info.plist').open('wb') as file:
        plistlib.dump(info, file)
    (resources / 'BUILD.json').write_text(json.dumps({'architecture': arch, 'python': version, 'minimum_macos': '13.0'}, indent=2))
    run('codesign', '--force', '--sign', '-', '--timestamp=none', app, stdout=subprocess.DEVNULL)
    run('codesign', '--verify', '--deep', '--strict', app)
    clean_environment = {'HOME': str(Path.home()), 'PATH': '/usr/bin:/bin', 'LANG': 'en_US.UTF-8'}
    run(resources / 'bin/agent-trace', '--help', env=clean_environment, stdout=subprocess.DEVNULL)
    print('Built ' + str(app), flush=True)


def install(app):
    target = Path.home() / 'Applications/Trace.app'
    target.parent.mkdir(exist_ok=True)
    if target.exists():
        with (target / 'Contents/Info.plist').open('rb') as file:
            if plistlib.load(file).get('CFBundleIdentifier') != BUNDLE_ID:
                raise SystemExit('Refusing to replace an unrelated app: ' + str(target))
    wrapper = Path.home() / '.local/bin/agent-trace'
    if wrapper.exists():
        previous = wrapper.read_text()
        if str(ROOT / 'agent_trace.py') not in previous and str(target) not in previous:
            raise SystemExit('Existing agent-trace command was not created by this workspace; leaving it unchanged.')
        backup = wrapper.with_name('agent-trace.before-mac-app')
        if not backup.exists():
            shutil.copy2(wrapper, backup)
    staging = target.with_name('Trace.app.installing')
    if staging.exists():
        raise SystemExit('An earlier installation is still staged: ' + str(staging))
    shutil.copytree(app, staging, symlinks=True)
    run('codesign', '--verify', '--deep', '--strict', staging)
    backup = target.with_name('.Trace.backup-' + str(time.time_ns()) + '.app')
    if target.exists():
        target.rename(backup)
        print('Previous app retained at ' + str(backup), flush=True)
    staging.rename(target)
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    cli = str(target / 'Contents/Resources/bin/agent-trace').replace("'", "'\"'\"'")
    temporary = wrapper.with_name('agent-trace.installing')
    temporary.write_text("#!/bin/sh\nexec '" + cli + "' \"$@\"\n")
    temporary.chmod(0o755)
    temporary.replace(wrapper)
    print('Installed ' + str(target), flush=True)
    print('CLI: ' + str(wrapper), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--install', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'mac/dist/Trace.app'
    build(output)
    if args.install:
        install(output)
