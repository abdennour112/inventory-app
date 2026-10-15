"""Rotate app admin/session secrets with rollback; never print secret values."""
from pathlib import Path
import json
import os
import secrets
import shutil
import subprocess
import tempfile

os.chdir(Path(__file__).resolve().parents[1])
compose = ['docker', 'compose']

def run(args, payload=None):
    print('+ ' + ' '.join(compose+args), flush=True)
    result = subprocess.run(compose+args, input=payload, text=True, capture_output=True)
    if result.returncode:
        # Output may contain private probe data; retain only the exit status.
        raise RuntimeError('Command failed with exit status '+str(result.returncode))
    return result.stdout

def write_secret(path, value, metadata):
    descriptor = os.open(str(path)+'.tmp', os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w') as stream:
        stream.write(value+'\n')
    os.chown(str(path)+'.tmp', metadata.st_uid, metadata.st_gid)
    os.replace(str(path)+'.tmp', path)

run(['build', 'app', 'maintenance'])
admin = Path('.secrets/admin_password')
session = Path('.secrets/session_key')
old_password = admin.read_text().strip()
probe = ['run', '--rm', '--no-deps', '-T', 'maintenance', 'python', 'tests/auth_probe.py']
old_cookie = json.loads(run(probe, json.dumps({'phase':'before','old_password':old_password})))['old_cookie']
backup = Path(tempfile.mkdtemp(prefix='.rotation-', dir='.secrets'))
for path in (admin, session):
    shutil.copy2(path, backup/path.name)
    os.chown(backup/path.name, path.stat().st_uid, path.stat().st_gid)
try:
    run(['stop', 'app'])
    for path in (admin, session):
        write_secret(path, secrets.token_urlsafe(36), path.stat())
    run(['run', '--rm', '--no-deps', '-T', 'maintenance', 'python', 'manage.py', 'reset-admin'])
    run(['up', '-d', '--force-recreate', 'app', '--wait', '--wait-timeout', '90'])
    result = run(probe, json.dumps({'phase':'after','old_password':old_password,
                                  'old_cookie':old_cookie,'new_password':admin.read_text().strip()}))
    print(result.strip())
except Exception:
    print('Rotation failed; restoring previous credentials.', flush=True)
    run(['stop', 'app'])
    for path in (admin, session):
        write_secret(path, (backup/path.name).read_text().strip(), (backup/path.name).stat())
    run(['run', '--rm', '--no-deps', '-T', 'maintenance', 'python', 'manage.py', 'reset-admin'])
    run(['up', '-d', '--force-recreate', 'app', '--wait', '--wait-timeout', '90'])
    raise
else:
    shutil.rmtree(backup)
    print('Rotation verified. New administrator password remains in .secrets/admin_password.')
