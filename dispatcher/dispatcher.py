import os
import traceback
from flask import Flask
from google.cloud import run_v2

app = Flask(__name__)

# These will be set by the gcloud run deploy command
GCP_PROJECT = os.environ.get("GCLOUD_PROJECT")
GCP_LOCATION = "us-central1"
JOB_NAME = os.environ.get("COLLECTOR_JOB_NAME")

@app.route("/", methods=["GET"])
def trigger_run_job():
    """Triggers the main Cloud Run Job."""
    try:
        print(f"Dispatcher received trigger. Executing Cloud Run Job: {JOB_NAME}")
        client = run_v2.JobsClient()
        
        job_path = f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/jobs/{JOB_NAME}"
        
        request = run_v2.RunJobRequest(
            name=job_path
        )
        operation = client.run_job(request=request)
        
        print(f"✅ Job execution started successfully.")
        
        return "Successfully triggered the Cloud Run Job.", 200
        
    except Exception as e:
        print(f"❌ Failed to trigger job: {e}")
        traceback.print_exc()
        return "Error triggering job.", 500