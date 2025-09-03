#!/bin/bash

set -euo pipefail

# 1) Load env
if [[ -f .env ]]; then
  export $(grep -v '^#' .env | xargs)
else
  echo "❌ .env not found. Create it from .env.example"
  exit 1
fi

# 2) Required vars
REQUIRED_VARS=(
  GCLOUD_PROJECT
  REGION
  DOCKER_COLLECTOR_JOB
  DOCKER_AI_JOB
  DOCKER_AI_DISPATCH
  DOCKER_COLLECTOR_DISPATCH
  GEMINI_API_KEY
  JOBRIGHT_EMAIL
  JOBRIGHT_PASSWORD
  GOOGLE_SHEET_ID
  RESUME_LATEX_FILE
)
for v in "${REQUIRED_VARS[@]}"; do
  if [[ -z "${!v:-}" ]]; then
    echo "❌ Missing env var: $v"
    exit 1
  fi
done

# Defaults
TOPIC_NAME=${TOPIC_NAME:-scraped-urls}
SCHEDULE=${SCHEDULE:-"00 12 * * 1-6"}
TIMEZONE=${TIMEZONE:-America/Denver}
DISPATCHER_SA="dispatcher-sa@$GCLOUD_PROJECT.iam.gserviceaccount.com"
COLLECTOR_SA="collector-sa@$GCLOUD_PROJECT.iam.gserviceaccount.com"
AI_ANALYZER_SA="ai-analyzer-sa@$GCLOUD_PROJECT.iam.gserviceaccount.com"
DISPATCHER_SVC="job-dispatcher"
TRIGGER_SVC="job-trigger-service"
COLLECTOR_JOB="job-collector"
AI_JOB="ai-analyzer-job"

echo "🧩 Project: $GCLOUD_PROJECT | Region: $REGION"
gcloud config set project "$GCLOUD_PROJECT" >/dev/null

# 3) Enable APIs
echo "🔧 Enabling APIs..."
gcloud services enable \
  run.googleapis.com \
  secretmanager.googleapis.com \
  pubsub.googleapis.com \
  eventarc.googleapis.com \
  cloudscheduler.googleapis.com \
  sheets.googleapis.com >/dev/null

# 4) Secrets (create or add new version)
echo "🔐 Creating/updating secrets..."
create_or_update_secret () {
  local name="$1" ; local data_file="$2"
  if gcloud secrets describe "$name" >/dev/null 2>&1; then
    gcloud secrets versions add "$name" --data-file="$data_file" >/dev/null
  else
    gcloud secrets create "$name" --data-file="$data_file" --replication-policy=automatic >/dev/null
  fi
}

# String secrets via stdin
echo -n "$GEMINI_API_KEY"     > .tmp.gemini
echo -n "$JOBRIGHT_EMAIL"     > .tmp.jremail
echo -n "$JOBRIGHT_PASSWORD"  > .tmp.jrpass
echo -n "$GOOGLE_SHEET_ID"    > .tmp.sheet

create_or_update_secret gemini-api-key     .tmp.gemini
create_or_update_secret jobright-email     .tmp.jremail
create_or_update_secret jobright-password  .tmp.jrpass
create_or_update_secret google-sheet-id    .tmp.sheet

# File secret
if [[ ! -f "$RESUME_LATEX_FILE" ]]; then
  echo "❌ RESUME_LATEX_FILE not found: $RESUME_LATEX_FILE"
  rm -f .tmp.* ; exit 1
fi
create_or_update_secret resume-latex "$RESUME_LATEX_FILE"

rm -f .tmp.*

# 5) Service Accounts
echo "👤 Creating service accounts (idempotent)..."
gcloud iam service-accounts create dispatcher-sa --display-name="Job Scout Dispatcher SA" || true
gcloud iam service-accounts create collector-sa  --display-name="Job Scout Collector SA"  || true
gcloud iam service-accounts create ai-analyzer-sa --display-name="Job Scout AI Analyzer SA" || true

echo "⏳ Waiting 5 seconds for service account propagation..."
sleep 5

# 6) IAM bindings
echo "🔐 Granting IAM roles..."

# Dispatcher: needs to run jobs with overrides (both collector + AI jobs)
gcloud projects add-iam-policy-binding "$GCLOUD_PROJECT" \
  --member="serviceAccount:$DISPATCHER_SA" \
  --role="roles/run.developer" >/dev/null

# Collector: needs Pub/Sub publish + secrets for JobRight creds
gcloud projects add-iam-policy-binding "$GCLOUD_PROJECT" \
  --member="serviceAccount:$COLLECTOR_SA" \
  --role="roles/pubsub.publisher" >/dev/null
for s in jobright-email jobright-password; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:$COLLECTOR_SA" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
done

# AI Analyzer: needs Secret Manager access to these 3
for s in gemini-api-key resume-latex google-sheet-id; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:$AI_ANALYZER_SA" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
done

for s in gemini-api-key resume-latex google-sheet-id; do
  gcloud secrets add-iam-policy-binding "$s" \
    --member="serviceAccount:$DISPATCHER_SA" \
    --role="roles/secretmanager.secretAccessor" >/dev/null
done

# 7) Pub/Sub
echo "📨 Ensuring Pub/Sub topic '$TOPIC_NAME'..."
gcloud pubsub topics create "$TOPIC_NAME" >/dev/null 2>&1 || true

# 8) Deploy Dispatcher service (HTTP endpoint to kick off collector executions)
echo "🚀 Deploying dispatcher service..."
gcloud run deploy "$DISPATCHER_SVC" \
  --image="$DOCKER_COLLECTOR_DISPATCH" \
  --platform=managed \
  --region="$REGION" \
  --allow-unauthenticated \
  --service-account="$DISPATCHER_SA" \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60s \
  --set-env-vars="GCLOUD_PROJECT=$GCLOUD_PROJECT,COLLECTOR_JOB_NAME=$COLLECTOR_JOB,SERVICE_REGION=$REGION" \
  --max-instances=2 >/dev/null
DISPATCHER_URL=$(gcloud run services describe "$DISPATCHER_SVC" --region="$REGION" --format="value(status.url)")

# 9) Deploy Collector job (scraper)
echo "🚀 Deploying collector job..."
gcloud run jobs deploy "$COLLECTOR_JOB" \
  --image="$DOCKER_COLLECTOR_JOB" \
  --region="$REGION" \
  --service-account="$COLLECTOR_SA" \
  --memory=8Gi \
  --cpu=4 \
  --task-timeout=1800s \
  --parallelism=1 \
  --set-env-vars="GCLOUD_PROJECT=$GCLOUD_PROJECT,TOPIC_NAME=$TOPIC_NAME" \
  --update-secrets="JOBRIGHT_EMAIL=jobright-email:latest,JOBRIGHT_PASSWORD=jobright-password:latest" >/dev/null

# 10) Deploy AI Analyzer job (uses Secret Manager programmatically)
echo "🚀 Deploying AI Analyzer job..."
gcloud run jobs deploy "$AI_JOB" \
  --image="$DOCKER_AI_JOB" \
  --region="$REGION" \
  --service-account="$AI_ANALYZER_SA" \
  --memory=4Gi \
  --cpu=2 \
  --task-timeout=1800s \
  --parallelism=1 \
  --update-secrets="GOOGLE_SHEET_ID=google-sheet-id:latest,RESUME_LATEX=resume-latex:latest,GEMINI_API_KEY=gemini-api-key:latest" \
  --set-env-vars="GCLOUD_PROJECT=$GCLOUD_PROJECT" >/dev/null

# Also grant invoker on the specific AI job (not strictly required with run.developer, but harmless)
gcloud run jobs add-iam-policy-binding "$AI_JOB" \
  --region="$REGION" \
  --member="serviceAccount:$DISPATCHER_SA" \
  --role="roles/run.invoker" >/dev/null || true

# 11) Deploy Job Trigger Service (receives Pub/Sub via Eventarc, triggers AI job with overrides)
echo "🚀 Deploying job-trigger-service..."
gcloud run deploy "$TRIGGER_SVC" \
  --image="$DOCKER_AI_DISPATCH" \
  --platform=managed \
  --region="$REGION" \
  --allow-unauthenticated \
  --service-account="$DISPATCHER_SA" \
  --memory=512Mi \
  --cpu=1 \
  --timeout=60s \
  --set-env-vars="GCLOUD_PROJECT=$GCLOUD_PROJECT,REGION=$REGION,AI_JOB_NAME=$AI_JOB" \
  --max-instances=5 >/dev/null
TRIGGER_URL=$(gcloud run services describe "$TRIGGER_SVC" --region="$REGION" --format="value(status.url)")

# 12) Eventarc trigger: Pub/Sub topic -> job-trigger-service
echo "⚡ Creating/Updating Eventarc trigger..."
if gcloud eventarc triggers describe scraped-urls-trigger --location="$REGION" >/dev/null 2>&1; then
  gcloud eventarc triggers update scraped-urls-trigger \
    --location="$REGION" \
    --destination-run-service="$TRIGGER_SVC" \
    --destination-run-region="$REGION" \
    --event-filters="type=google.cloud.pubsub.topic.v1.messagePublished" \
    --transport-topic="$TOPIC_NAME" \
    --service-account="$DISPATCHER_SA" >/dev/null
else
  gcloud eventarc triggers create scraped-urls-trigger \
    --location="$REGION" \
    --destination-run-service="$TRIGGER_SVC" \
    --destination-run-region="$REGION" \
    --event-filters="type=google.cloud.pubsub.topic.v1.messagePublished" \
    --transport-topic="$TOPIC_NAME" \
    --service-account="$DISPATCHER_SA" >/dev/null
fi

# 13) Cloud Scheduler -> dispatcher service
echo "⏰ Creating/Updating Cloud Scheduler job..."
if gcloud scheduler jobs describe job-scout-scheduler --location="$REGION" >/dev/null 2>&1; then
  gcloud scheduler jobs update http job-scout-scheduler \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --time-zone="$TIMEZONE" \
    --uri="$DISPATCHER_URL" \
    --http-method=GET >/dev/null
else
  gcloud scheduler jobs create http job-scout-scheduler \
    --location="$REGION" \
    --schedule="$SCHEDULE" \
    --time-zone="$TIMEZONE" \
    --uri="$DISPATCHER_URL" \
    --http-method=GET \
    --description="Triggers the Job Scout dispatcher" >/dev/null
fi

echo
echo "🎉 Deployment complete"
echo "• Dispatcher URL:            $DISPATCHER_URL"
echo "• Job Trigger Service URL:   $TRIGGER_URL"
echo "• Pub/Sub Topic:             $TOPIC_NAME"
echo "• Collector Job:             $COLLECTOR_JOB"
echo "• AI Analyzer Job:           $AI_JOB"
echo "• Eventarc Trigger:          scraped-urls-trigger"
echo "• Scheduler:                 $SCHEDULE ($TIMEZONE)"
echo
echo "IMPORTANT: Share your Google Sheet with:"
echo "  $AI_ANALYZER_SA  (Editor, ✅ Notify, Send)"