# Operating the lab

## Open and sign in

On the Debian VM, open `https://inventory.lab.test`. Username: `admin`.
Read the generated password locally from `~/inventory-app/.secrets/admin_password`.
Do not paste it into chat or publish it. The local CA is trusted on this VM only.
Windows needs its own hostname mapping and explicit trust setup to use this URL.

## Everyday commands

```bash
cd ~/inventory-app
sudo docker compose ps
sudo docker compose logs --tail=100 app
sudo docker compose logs --tail=100 db
sudo docker compose restart app
sudo docker compose stop
sudo docker compose up -d --wait
```

`stop` stops containers and keeps data. Never use `down -v` on data you want to keep;
`-v` removes the named database volume.

## Backups

```bash
cd ~/inventory-app
sudo bash scripts/backup.sh
```

Backups are under `backups/`, excluded from Git, with a checksum file beside each.
The cron definition is `/etc/cron.d/inventory-backup`; output goes to
`/var/log/inventory-backup.log`. These are local backups only. Plan external storage
and a retention policy before using this beyond a small demonstration.

Restore to a new database and compare its data before considering a live recovery.
Do not overwrite the live database to test a backup. The command guide lists the steps.

## HTTPS and logs

Nginx site: `/etc/nginx/sites-available/inventory`.

App logs: `sudo docker compose logs app`.

Proxy logs: `/var/log/nginx/inventory-access.log` and `inventory-error.log`.

The certificate expires after one year; the private lab CA lasts ten years.
These certificates are for the local demonstration. A public domain deployment
needs a suitable publicly trusted certificate and its renewal process.

## Limits

One administrator role; no self-service password reset or staff permission model.
Failed login attempts are limited by username but have not undergone abuse testing.
Movement history is append-only through the UI; a database administrator can change it.
The demo does not provide payment processing, tax reporting, or a legal accounting ledger.
Container recreation is tested separately from a full VM reboot. A restart policy
alone does not prove successful recovery after a host reboot.
