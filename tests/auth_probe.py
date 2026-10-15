"""Private maintenance probe. Input and before-result must never be logged."""
import json
import re
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import app

data = json.load(sys.stdin)
base = 'https://localhost'

def login(password):
    client = app.test_client()
    page = client.get('/login', base_url=base)
    token = re.search(r'name="csrf_token" value="([^"]+)"', page.text).group(1)
    response = client.post('/login', base_url=base, headers={'Referer': base+'/login'},
                           data={'username': 'admin', 'password': password, 'csrf_token': token})
    return client, response

if data['phase'] == 'before':
    client, response = login(data['old_password'])
    assert response.status_code == 302, 'Existing administrator login failed'
    assert client.get('/', base_url=base).status_code == 200
    print(json.dumps({'old_cookie': client.get_cookie('session').value}))
else:
    client, response = login(data['old_password'])
    assert response.status_code == 401, 'Old password was not rejected'
    client, response = login(data['new_password'])
    assert response.status_code == 302, 'New password was not accepted'
    assert client.get('/', base_url=base).status_code == 200
    old = app.test_client()
    old.set_cookie('session', data['old_cookie'])
    assert old.get('/', base_url=base).status_code == 302, 'Old session was not revoked'
    print('PASS: old administrator password rejected; new password accepted; old session revoked.')
