# Verified deployment — 2026-10-12

The inventory application is deployed on the local Debian 13 VM with Docker
Compose, PostgreSQL 17 and Nginx. Deployment commands ran in visible Debian
terminals and the administrator password was entered locally.

## Passed

- 39 integration checks against real PostgreSQL, including authentication, CSRF,
  invalid input, unique SKUs, HTML escaping, stock arithmetic, insufficient stock,
  duplicate submissions, concurrent sales, low-stock filtering and logout.
- The same checks passed again after secure session cookies were enabled.
- A database backup was restored to a separate temporary database. Row counts
  and data fingerprints for categories, products and movements matched.
- Both app and database containers were recreated. Inventory fingerprints were
  unchanged afterward, demonstrating persistence through the named volume.
- `https://inventory.lab.test/health` passed certificate verification and
  returned `database: ok` and `status: ok`. Certificate checking was not bypassed.
- HTTP redirected to HTTPS. Nginx configuration validation passed.
- App and database containers reported healthy.
- Source and documentation were saved in a local Git repository on Debian.

## Evidence

See `docs/evidence/` for the integration results, restore and persistence
comparisons, HTTPS response, redirect headers, image information and backup schedule.

## Limits and remaining work

- The dashboard screenshot shows the actual application with fictional demo data.
- The daily backup job is configured for 02:30 in the VM timezone (CDT at test
  time). Its scheduled execution has not yet been observed.
- A full VM reboot recovery test has not been performed. Container recreation
  is a separate, completed test.
- The certificate authority is private to this lab. Public certificate issuance
  and Windows hostname/trust setup are not part of this verification.
- These are scoped application and deployment checks, not a penetration test or production load test. Base OS and container OS packages were not covered by the Python advisory scan.
- This is a local portfolio project with fictional demo products. It has not
  been deployed on a public server. This repository publishes source and documentation only.

## Security update verified on 2026-10-13

- All 39 integration checks passed again after the security update.
- The web container runs as UID 1000 and has no mounted administrator password.
- A separate database role has data permissions, but no superuser, role-creation, database-creation, replication or schema-creation privileges.
- Administrator password and session signing key were rotated. The old password failed, the new password worked, and the old authenticated session was rejected.
- HTTPS certificate validation, secure cookie flags and HTTP-to-HTTPS redirects passed.
- A fresh database backup was created after the update.
- pip-audit checked all 14 pinned Python dependencies and reported no known vulnerabilities on 2026-10-13. The Docker build installs those pinned versions.
- The public release excludes runtime secrets, backups, private SSH helpers and agent coordination files. It starts with clean Git history.

The dependency report is in `docs/evidence/python-dependency-audit.json`. Credentials remain private on the lab machine. Advisory results are time-specific and do not rule out unknown vulnerabilities.
