import os
import json
import base64
import traceback
import uuid
from flask import Flask, request
from google.cloud import run_v2

app = Flask(__name__)

GCP_PROJECT = os.environ.get("GCLOUD_PROJECT")
GCP_LOCATION = os.environ.get("REGION", "us-central1")
AI_JOB_NAME = os.environ.get("AI_JOB_NAME", "ai-analyzer-job")

@app.route("/", methods=["POST"])
def trigger_ai_analyzer():
    """Receives Pub/Sub message and triggers AI Analyzer job"""
    envelope = request.get_json()
    if not envelope or "message" not in envelope:
        return "Bad Request", 400

    pubsub_message = envelope["message"]
    message_id = pubsub_message.get("messageId", "unknown")
    
    try:
        data_str = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        data = json.loads(data_str)
        urls_to_process = data.get("urls", [])
        
        if not urls_to_process:
            print(f"📝 Message {message_id}: Empty batch received.")
            return "Empty batch received.", 200

        print(f"🚀 Message {message_id}: Triggering AI Analyzer Job for {len(urls_to_process)} URLs")
        
        # Generate a unique batch ID
        batch_id = f"batch-{uuid.uuid4().hex[:8]}"
        
        client = run_v2.JobsClient()
        job_path = f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/jobs/{AI_JOB_NAME}"
        
        # Pass URLs as command arguments
        args = [
            "--urls-json", json.dumps(urls_to_process),
            "--batch-id", batch_id
        ]
        
        run_job_request = run_v2.RunJobRequest(
            name=job_path,
            overrides=run_v2.RunJobRequest.Overrides(
                container_overrides=[
                    run_v2.RunJobRequest.Overrides.ContainerOverride(
                        args=args
                    )
                ]
            )
        )
        
        operation = client.run_job(request=run_job_request)
        print(f"✅ Message {message_id}: AI Analyzer Job {batch_id} started successfully")
        
        return f"AI Analyzer Job triggered: {batch_id}", 200
        
    except Exception as e:
        print(f"❌ Message {message_id}: Error triggering AI job: {e}")
        traceback.print_exc()
        return "Error processed and logged.", 200  # Return 200 to prevent retries

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))