# Supabase backups on Google Cloud

Backs up your Supabase database at 03:00 and 15:00 Israel time to a private Cloud Storage bucket in `me-west1`.

| Copy | When | Kept for |
|---|---|---|
| `rolling/` | Every run | 14 days |
| `weekly/` | Sunday morning run | 8 weeks |
| `monthly/` | Morning run on the 1st | 12 months |

## Set up

You need the `gcloud` CLI, logged in with Owner access to the project, and billing enabled.

1. Find your Postgres major version. In the Supabase SQL editor, run `show server_version;`.
2. Copy the connection string from Supabase: **Connect > Session pooler**. Delete `:[YOUR-PASSWORD]` from it, so it looks like `postgresql://postgres.REF@HOST.pooler.supabase.com:5432/postgres`.
3. Optional: create a free check at healthchecks.io with a 12-hour period and a 1-hour grace time.
4. Deploy. Keep `Dockerfile.backup`, `backup.sh` and `lifecycle.json` in the same folder as `deploy.sh`. You can run it from any folder:

   ```bash
   PROJECT_ID=medi-shift-prod \
   SUPABASE_DB_URL='postgresql://postgres.REF@HOST.pooler.supabase.com:5432/postgres' \
   PG_MAJOR=17 \
   HEALTHCHECK_URL=https://hc-ping.com/your-uuid \
   bash deploy.sh
   ```

The password comes from the existing `supabase-postgres-prod` secret, which must contain only the password. `deploy.sh` doesn't read or change that secret. It only lets the backup job read it. To use a different secret, add `SECRET=its-name`.

The script finishes by running a real backup and listing it. Leave `HEALTHCHECK_URL` out if you skipped step 3, but then set up a Cloud Monitoring alert for failed `supabase-backup` executions.

If `gcloud builds submit` fails with a permissions error, your project's Cloud Build service account needs access to build. Grant the role named in the error and run `deploy.sh` again.

## Common changes

- **New database password:** Add it as a new version of `supabase-postgres-prod`. The next run uses it.

- **Supabase upgrades Postgres:** Run `deploy.sh` again with the same settings and the new `PG_MAJOR`.
- **You add a schema:** Update the job. Without this, the new schema isn't backed up.

  ```bash
  gcloud run jobs update supabase-backup --region=me-west1 \
    --update-env-vars='^|^DUMP_SCHEMAS=public auth storage my_schema'
  ```

- **Run a backup now:**

  ```bash
  gcloud run jobs execute supabase-backup --region=me-west1 --wait
  ```

## Restore

Always restore into a new database first, not over production.

Get a backup:

```bash
gcloud storage ls gs://YOUR_PROJECT_ID-supabase-backups/rolling/
gcloud storage cp gs://YOUR_PROJECT_ID-supabase-backups/rolling/FILE.dump backup.dump
```

### Into an empty Postgres (use this for restore tests)

```bash
docker run -d --name restore-test -e POSTGRES_PASSWORD=test -p 54320:5432 postgres:17
TARGET=postgresql://postgres:test@localhost:54320/postgres

# The public schema already exists in a new database, so skip creating it.
pg_restore --list backup.dump | grep -v ' SCHEMA - public ' > restore.list
pg_restore --no-owner --no-privileges --use-list=restore.list --exit-on-error -d "$TARGET" backup.dump
```

Then compare row counts for your main tables with production. Use `postgres:` with your own major version, and a `pg_restore` of that version or newer.

### Into a new Supabase project

A new project already has its own `auth` and `storage` tables, so restore only their rows.

1. Enable any extensions you use (**Database > Extensions**). The backup doesn't include them.
2. Set `TARGET` to the new project's session pooler string.
3. Restore `auth` and `storage` rows first, because your tables may reference `auth.users`:

   ```bash
   pg_restore --data-only --no-owner --no-privileges --schema=auth --exit-on-error -d "$TARGET" backup.dump
   pg_restore --data-only --no-owner --no-privileges --schema=storage --exit-on-error -d "$TARGET" backup.dump
   ```

4. Restore `public`:

   ```bash
   pg_restore --no-owner --no-privileges --schema=public --exit-on-error -d "$TARGET" backup.dump
   ```

5. Recreate anything of your own attached to `auth` or `storage` tables, such as a trigger on `auth.users` or policies on `storage.objects`. Steps 3 and 4 don't restore those.
6. Re-upload Storage files, and re-enter project settings such as auth providers, API keys and secrets. None of these are in the backup.

### Restore one table

```bash
pg_restore --no-owner --no-privileges --data-only --schema=public --table=orders -d "$TARGET" backup.dump
```
