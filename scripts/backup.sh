#!/bin/sh
# Daily encrypted backup of the database and the MinIO file store.
# Usage: BACKUP_PASSPHRASE=... sh scripts/backup.sh      (schedule with cron: 0 2 * * *)
# Output: backups/vayu-YYYYmmdd-HHMMSS.tar.enc (AES-256, PBKDF2). Keep the passphrase off this server.
set -eu
: "${BACKUP_PASSPHRASE:?Set BACKUP_PASSPHRASE}"
COMPOSE="${COMPOSE:-docker-compose}"
STAMP=$(date +%Y%m%d-%H%M%S)
WORK=$(mktemp -d)
mkdir -p backups
$COMPOSE exec -T db pg_dump -U vayu -d vayu --format=custom > "$WORK/db.dump"
$COMPOSE exec -T minio tar -C /data -cf - . > "$WORK/files.tar"
tar -C "$WORK" -cf - db.dump files.tar | openssl enc -aes-256-cbc -pbkdf2 -salt -pass env:BACKUP_PASSPHRASE -out "backups/vayu-$STAMP.tar.enc"
rm -rf "$WORK"
# keep 180 days of backups
find backups -name 'vayu-*.tar.enc' -mtime +180 -delete
echo "Backup written: backups/vayu-$STAMP.tar.enc"
