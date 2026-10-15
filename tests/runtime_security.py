"""Verify restrictions from inside the running application container."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import os
import psycopg
from app import connect

assert os.geteuid() == 1000, 'Application must run without root'
assert not Path('/run/secrets/admin_password').exists(), 'Admin password mounted in web container'
assert not Path('/run/secrets/app_db_password').exists(), 'Unexpected maintenance secret mount'
with connect() as db:
    role = db.execute('SELECT current_user AS name, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=current_user').fetchone()
    assert role['name'] == 'inventory_web'
    assert not any(role[key] for key in role if key != 'name')
    assert not db.execute("SELECT has_schema_privilege(current_user,'public','CREATE') AS allowed").fetchone()['allowed']
    assert not db.execute("SELECT pg_has_role(current_user,'inventory','MEMBER') AS allowed").fetchone()['allowed']
try:
    with connect() as db:
        db.execute('CREATE TABLE public.must_not_be_created (id integer)')
        raise AssertionError('Application can create schema objects')
except psycopg.errors.InsufficientPrivilege:
    pass
print('PASS: non-root app; administrator secret absent; runtime role has no administrative or schema-creation privileges.')
