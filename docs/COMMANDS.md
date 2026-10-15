# Commands used and their purpose

Commands run inside the Debian VM. The live installer runs once through `sudo`,
so its displayed Docker commands do not need another `sudo` prefix. For manual
operations as the normal user, add `sudo` to Docker and system administration commands.

## 1. Baseline and recovery copy

`docker --version` / `docker compose version`: confirm installed tooling.

`curl --fail http://127.0.0.1:8001/health`: confirm the existing starter responds.

`tar -czf <private-backup> -C "$HOME" inventory-app`: save the starter files.

`tar -xzvf <source-archive> -C "$HOME/inventory-app"`: install source files and
show every filename in the terminal. This archive contains no runtime credentials.

## 2. Credentials and configuration

`python3 scripts/init-secrets.py`: generate random database, session and admin
secrets once, with owner-only file permissions. Existing values are preserved.

`docker compose config --quiet`: validate the configuration without dumping
resolved settings or credentials to the terminal.

## 3. Database and app

`docker compose up -d db --wait`: download/start PostgreSQL and wait for its health check.

`docker compose build app maintenance`: build the application image from the Dockerfile.

`docker compose run --rm maintenance python manage.py init`: create schema version 1 and
the administrator in a temporary application container, then remove that container.

`docker compose run --rm maintenance python manage.py seed`: add fictional demo products;
existing SKUs are left alone. This is optional on a real deployment.

`docker compose up -d --wait`: start the application in the background, wait for
health checks, and return. Containers keep running after the terminal is closed.

`docker compose ps`: show each container's state, health and published ports.

## 4. Behavior and data protection

`docker compose exec -T app python tests/integration.py`: run meaningful application
checks against the running database. `-T` disables terminal allocation for readable logs.

`bash scripts/backup.sh`: run `pg_dump -Fc`, save a private backup and record its SHA-256.

`docker compose exec -T db createdb -U inventory <temporary-db>`: create a restore target.

`docker compose exec -T db pg_restore --exit-on-error -U inventory -d <temporary-db> < <backup>`:
restore the backup into that target, stopping on SQL errors.

`docker compose exec -T -e DB_NAME=<temporary-db> app python tests/fingerprint.py`:
calculate row counts and data fingerprints for categories, products and movements.

`diff -u <live-fingerprint> <restored-fingerprint>`: verify restored data matches.

`docker compose exec -T db dropdb -U inventory <temporary-db>`: remove only the temporary
restore-test database after comparison. Never substitute the live `inventory` database.

`docker compose up -d --force-recreate --wait`: replace containers while retaining the
named volume. Comparing fingerprints before and after checks persistence.

## 5. Local HTTPS

`openssl req`: generate a private lab certificate authority and a server key/request.

`openssl x509 -req`: sign a certificate containing `inventory.lab.test` as its DNS SAN.

`update-ca-certificates`: register the public lab CA certificate in Debian's trust store.

`certutil -A`: add the same public CA to the user's Firefox certificate database.
The CA private key remains private under `/etc/nginx/inventory-pki/`.

`nginx -t`: check all Nginx configuration syntax and referenced certificate files.

`systemctl reload nginx`: apply the validated configuration.

`curl --fail https://inventory.lab.test/health`: verify HTTPS hostname, trust and app health.
No `-k` / insecure certificate bypass is used.

`curl --head http://inventory.lab.test`: verify the HTTP-to-HTTPS redirect.

## 6. Evidence and maintenance

`docker compose exec -T app pip freeze`: record resolved dependency versions.

`docker compose images`: record the images used in the lab.

`git init`, `git add .`, `git commit`: save source and documentation locally with
secret files, private backups and runtime `.env` ignored.

The installer configures a daily backup at 02:30 in the VM's own timezone.
Successful manual backup testing does not prove the scheduled job has fired.
