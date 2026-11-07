#!/usr/bin/env bash
#
# Creates or updates everything in Google Cloud. Safe to run again after a
# change. Keep Dockerfile.backup, backup.sh and lifecycle.json in the same
# folder as this script. You can run it from any folder:
#
#   PROJECT_ID=my-project \
#   SUPABASE_DB_URL='postgresql://postgres.REF@HOST.pooler.supabase.com:5432/postgres' \
#   PG_MAJOR=17 bash deploy.sh
#
# The URL must not contain the password. The password stays in the existing
# Secret Manager secret, and this script never reads or changes it.

set -Eeuo pipefail

PROJECT_ID="${PROJECT_ID:?Set PROJECT_ID to your Google Cloud project ID}"
SUPABASE_DB_URL="${SUPABASE_DB_URL:?Set SUPABASE_DB_URL to the session pooler string, without the password}"
if [[ "$SUPABASE_DB_URL" =~ ://[^/@]*:[^/@]*@ ]]; then
  echo "Remove the password from SUPABASE_DB_URL. It stays in Secret Manager." >&2
  exit 1
fi
if [[ "$SUPABASE_DB_URL" != *"pooler.supabase.com:5432/"* ]]; then
  echo "SUPABASE_DB_URL should be the session pooler string (pooler.supabase.com, port 5432)." >&2
  exit 1
fi
PG_MAJOR="${PG_MAJOR:-17}"
REGION="${REGION:-me-west1}"
BUCKET="${BUCKET:-${PROJECT_ID}-supabase-backups}"
SCHEDULE="${SCHEDULE:-0 3,15 * * *}"
TIME_ZONE="${TIME_ZONE:-Asia/Jerusalem}"
HEALTHCHECK_URL="${HEALTHCHECK_URL:-}"

# The backup files are found next to this script, so it can run from any folder.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE="${DOCKERFILE:-Dockerfile.backup}"
for required in "$DOCKERFILE" backup.sh lifecycle.json; do
  if [[ ! -f "${SCRIPT_DIR}/${required}" ]]; then
    echo "${required} must be in the same folder as deploy.sh (${SCRIPT_DIR})." >&2
    exit 1
  fi
done

JOB="supabase-backup"
SCHEDULER_JOB="supabase-backup-schedule"
SECRET="${SECRET:-supabase-postgres-prod}"
REPOSITORY="supabase-backup"
JOB_SA="supabase-backup-job@${PROJECT_ID}.iam.gserviceaccount.com"
SCHEDULER_SA="supabase-backup-scheduler@${PROJECT_ID}.iam.gserviceaccount.com"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${REPOSITORY}/backup:$(date -u +%Y%m%d%H%M%S)"

step() { echo; echo "==> $*"; }

ensure_service_account() {
  local name="$1" email="$2"
  if ! gcloud iam service-accounts describe "$email" >/dev/null 2>&1; then
    gcloud iam service-accounts create "$name" --display-name="$name"
    sleep 15 # New service accounts take a moment to become visible to IAM.
  fi
}

gcloud config set project "$PROJECT_ID" >/dev/null

step "Enabling Google Cloud APIs"
gcloud services enable \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  cloudscheduler.googleapis.com \
  run.googleapis.com \
  secretmanager.googleapis.com \
  storage.googleapis.com

step "Creating the bucket and retention rules"
if ! gcloud storage buckets describe "gs://${BUCKET}" >/dev/null 2>&1; then
  gcloud storage buckets create "gs://${BUCKET}" \
    --location="$REGION" \
    --default-storage-class=STANDARD \
    --uniform-bucket-level-access \
    --public-access-prevention
fi
gcloud storage buckets update "gs://${BUCKET}" --lifecycle-file="${SCRIPT_DIR}/lifecycle.json"

step "Creating service accounts"
ensure_service_account supabase-backup-job "$JOB_SA"
ensure_service_account supabase-backup-scheduler "$SCHEDULER_SA"

step "Checking the existing password secret"
if ! gcloud secrets describe "$SECRET" >/dev/null 2>&1; then
  echo "Secret '${SECRET}' was not found in project ${PROJECT_ID}." >&2
  exit 1
fi

step "Granting the backup job its permissions (no delete rights)"
gcloud secrets add-iam-policy-binding "$SECRET" \
  --member="serviceAccount:${JOB_SA}" \
  --role=roles/secretmanager.secretAccessor \
  --condition=None >/dev/null
for role in roles/storage.objectCreator roles/storage.objectViewer; do
  gcloud storage buckets add-iam-policy-binding "gs://${BUCKET}" \
    --member="serviceAccount:${JOB_SA}" \
    --role="$role" >/dev/null
done

step "Building the container image"
if ! gcloud artifacts repositories describe "$REPOSITORY" --location="$REGION" >/dev/null 2>&1; then
  gcloud artifacts repositories create "$REPOSITORY" \
    --repository-format=docker \
    --location="$REGION"
fi
# Upload only the two files the image needs, never the rest of your project.
build_dir="$(mktemp -d)"
build_config="$(mktemp)"
trap 'rm -rf "$build_dir" "$build_config"' EXIT
cp "${SCRIPT_DIR}/${DOCKERFILE}" "${build_dir}/Dockerfile"
cp "${SCRIPT_DIR}/backup.sh" "${build_dir}/backup.sh"
cat >"$build_config" <<EOF
steps:
  - name: gcr.io/cloud-builders/docker
    args: [build, --build-arg, PG_MAJOR=${PG_MAJOR}, -t, "${IMAGE}", .]
images: ["${IMAGE}"]
EOF
gcloud builds submit --config="$build_config" "$build_dir"

step "Deploying the Cloud Run job"
gcloud run jobs deploy "$JOB" \
  --image="$IMAGE" \
  --region="$REGION" \
  --service-account="$JOB_SA" \
  --set-secrets="SUPABASE_DB_PASSWORD=${SECRET}:latest" \
  --set-env-vars="SUPABASE_DB_URL=${SUPABASE_DB_URL},BACKUP_BUCKET=${BUCKET},BACKUP_TZ=${TIME_ZONE},HEALTHCHECK_URL=${HEALTHCHECK_URL}" \
  --tasks=1 \
  --max-retries=1 \
  --task-timeout=15m \
  --cpu=1 \
  --memory=1Gi

step "Scheduling the job"
gcloud run jobs add-iam-policy-binding "$JOB" \
  --region="$REGION" \
  --member="serviceAccount:${SCHEDULER_SA}" \
  --role=roles/run.invoker >/dev/null

job_uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${JOB}:run"
if gcloud scheduler jobs describe "$SCHEDULER_JOB" --location="$REGION" >/dev/null 2>&1; then
  scheduler_action=update
else
  scheduler_action=create
fi
gcloud scheduler jobs "$scheduler_action" http "$SCHEDULER_JOB" \
  --location="$REGION" \
  --schedule="$SCHEDULE" \
  --time-zone="$TIME_ZONE" \
  --uri="$job_uri" \
  --http-method=POST \
  --oauth-service-account-email="$SCHEDULER_SA"

step "Running a first backup"
gcloud run jobs execute "$JOB" --region="$REGION" --wait

step "Backups now in the bucket"
gcloud storage ls -l "gs://${BUCKET}/rolling/"

echo
echo "Done. Backups run on '${SCHEDULE}' (${TIME_ZONE})."
