#!/usr/bin/env bash
#
# Dumps the Supabase database, checks the dump is readable, and uploads it to
# Cloud Storage. Runs as a Cloud Run job.
#
# Required environment variables:
#   SUPABASE_DB_URL       Session pooler connection string, without the password
#   SUPABASE_DB_PASSWORD  Database password (from Secret Manager)
#   BACKUP_BUCKET         Bucket name, without gs://
#
# Optional environment variables:
#   DUMP_SCHEMAS        Space-separated schemas to dump
#   EXCLUDE_TABLE_DATA  Space-separated tables to keep the structure of but not
#                       the rows. The defaults are managed by Supabase, and a new
#                       project creates its own rows in them.
#   MIN_DUMP_BYTES      Fail if the dump is smaller than this
#   BACKUP_TZ           Time zone used to decide weekly and monthly copies
#   HEALTHCHECK_URL     healthchecks.io ping URL
#   WORK_DIR            Where to write the dump temporarily

set -Eeuo pipefail

: "${SUPABASE_DB_URL:?SUPABASE_DB_URL is not set}"
: "${SUPABASE_DB_PASSWORD:?SUPABASE_DB_PASSWORD is not set}"
: "${BACKUP_BUCKET:?BACKUP_BUCKET is not set}"

# pg_dump reads the password from PGPASSWORD. A secret saved from a text file
# often ends in a newline, which would make the login fail.
export PGPASSWORD="${SUPABASE_DB_PASSWORD%$'\n'}"
unset SUPABASE_DB_PASSWORD

DUMP_SCHEMAS="${DUMP_SCHEMAS:-public auth storage}"
EXCLUDE_TABLE_DATA="${EXCLUDE_TABLE_DATA:-auth.schema_migrations storage.migrations}"
MIN_DUMP_BYTES="${MIN_DUMP_BYTES:-10240}"
BACKUP_TZ="${BACKUP_TZ:-Asia/Jerusalem}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"
WORK_DIR="${WORK_DIR:-/tmp}"

log() { echo "[backup] $*"; }

ping_healthcheck() {
  # A monitoring outage must never fail a good backup.
  [[ -n "$HEALTHCHECK_URL" ]] || return 0
  curl -fsS -m 10 --retry 3 -o /dev/null "${HEALTHCHECK_URL}${1:-}" || true
}

on_error() {
  log "FAILED at line $1"
  ping_healthcheck /fail
}
trap 'on_error $LINENO' ERR

timestamp="$(date -u +%Y-%m-%dT%H-%M-%SZ)"
filename="supabase-${timestamp}.dump"
dump_path="${WORK_DIR}/${filename}"
toc_path="${dump_path}.toc"
trap 'rm -f "$dump_path" "$toc_path"' EXIT

dump_args=(--format=custom --file="$dump_path")
for schema in $DUMP_SCHEMAS; do
  dump_args+=("--schema=$schema")
done
for table in $EXCLUDE_TABLE_DATA; do
  dump_args+=("--exclude-table-data=$table")
done

log "Dumping schemas: $DUMP_SCHEMAS"
pg_dump "${dump_args[@]}" "$SUPABASE_DB_URL"

dump_bytes="$(wc -c <"$dump_path" | tr -d ' ')"
log "Dump size: ${dump_bytes} bytes"
if ((dump_bytes < MIN_DUMP_BYTES)); then
  log "Dump is smaller than MIN_DUMP_BYTES (${MIN_DUMP_BYTES})"
  false
fi

# Reads the archive's table of contents. This catches a corrupt file, but it does
# not prove the data restores, which is why the README has a restore test.
pg_restore --list "$dump_path" >"$toc_path"
table_data_entries="$(grep -c ' TABLE DATA ' "$toc_path" || true)"
log "Tables with data in the dump: ${table_data_entries}"
if ((table_data_entries == 0)); then
  log "Dump contains no table data"
  false
fi

destinations=("gs://${BACKUP_BUCKET}/rolling/${filename}")

# Only the morning run feeds the long-term copies, so there is one per period.
local_hour="$(TZ="$BACKUP_TZ" date +%H)"
if ((10#$local_hour < 12)); then
  if [[ "$(TZ="$BACKUP_TZ" date +%u)" == "7" ]]; then
    destinations+=("gs://${BACKUP_BUCKET}/weekly/${filename}")
  fi
  if [[ "$(TZ="$BACKUP_TZ" date +%d)" == "01" ]]; then
    destinations+=("gs://${BACKUP_BUCKET}/monthly/${filename}")
  fi
fi

for destination in "${destinations[@]}"; do
  log "Uploading to ${destination}"
  gcloud storage cp --quiet "$dump_path" "$destination"
done

ping_healthcheck
log "Done"
