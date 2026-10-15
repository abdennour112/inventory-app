"""Create private local secrets once; never print them."""
from pathlib import Path
import os
import secrets
folder=Path('.secrets')
folder.mkdir(mode=0o700,exist_ok=True)
os.chmod(folder,0o700)
for name in ('db_password','app_db_password','session_key','admin_password'):
    path=folder/name
    if not path.exists():
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(descriptor,'w') as stream:
            stream.write(secrets.token_urlsafe(36)+'\n')
    os.chmod(path,0o600)
print('Four local secrets exist with owner-only permissions. Values omitted.')
