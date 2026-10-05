#!/bin/sh
# Restore the newest (or a named) encrypted backup.
# Usage: BACKUP_PASSPHRASE=... sh scripts/restore.sh [backups/vayu-....tar.enc]
# Run a restore drill on a spare machine after every change to the backup job.
set -eu
: "${BACKUP_PASSPHRASE:?Set BACKUP_PASSPHRASE}"
COMPOSE="${COMPOSE:-docker-compose}"
FILE="${1:-$(ls -1t backups/vayu-*.tar.enc | head -1)}"
WORK=$(mktemp -d)
openssl enc -d -aes-256-cbc -pbkdf2 -pass env:BACKUP_PASSPHRASE -in "$FILE" | tar -C "$WORK" -xf -
$COMPOSE stop api worker
$COMPOSE exec -T db pg_restore -U vayu -d vayu --clean --if-exists --no-owner < "$WORK/db.dump"
$COMPOSE exec -T minio sh -c 'rm -rf /data/* && tar -C /data -xf -' < "$WORK/files.tar"
$COMPOSE start api worker
rm -rf "$WORK"
echo "Restored from $FILE. Log in as the Auditor and press 'Verify chain' to confirm the audit trail is intact."
