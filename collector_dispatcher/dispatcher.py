import os
import traceback
from flask import Flask
from google.cloud import run_v2

app = Flask(__name__)

# These will be set by the gcloud run deploy command
GCP_PROJECT = os.environ.get("GCLOUD_PROJECT")
GCP_LOCATION = os.environ.get("SERVICE_REGION")
JOB_NAME = os.environ.get("COLLECTOR_JOB_NAME")

@app.route("/", methods=["GET"])
def trigger_run_job():
    """Triggers multiple Cloud Run Job instances with different parameters."""
    try:
        print(f"Dispatcher received trigger. Executing multiple instances of Cloud Run Job: {JOB_NAME}")
        client = run_v2.JobsClient()
        
        job_path = f"projects/{GCP_PROJECT}/locations/{GCP_LOCATION}/jobs/{JOB_NAME}"
        
        # Define the job instances to run
        job_configs = [
            {
                "name": "top-half",
                "start_index": 0,
                "end_index": 75,
                "description": "Processing jobs 1-75"
            },
            {
                "name": "bottom-half", 
                "start_index": 75,
                "end_index": 150,
                "description": "Processing jobs 76-150"
            }
        ]
        
        operations = []

        base_env_vars = [
            run_v2.EnvVar(name="GCLOUD_PROJECT", value=GCP_PROJECT),
            run_v2.EnvVar(name="COLLECTOR_JOB_NAME", value=JOB_NAME),
        ]
        
        for config in job_configs:
            print(f"🚀 Starting job instance: {config['description']}")
            
            # Create environment variables for this instance
            env_vars = base_env_vars + [
                run_v2.EnvVar(name="START_INDEX", value=str(config["start_index"])),
                run_v2.EnvVar(name="END_INDEX", value=str(config["end_index"])),
                run_v2.EnvVar(name="INSTANCE_NAME", value=config["name"])
            ]
            
            # Create the job execution request with custom environment variables
            request = run_v2.RunJobRequest(
                name=job_path,
                overrides=run_v2.RunJobRequest.Overrides(
                    container_overrides=[
                        run_v2.RunJobRequest.Overrides.ContainerOverride(
                            env=env_vars
                        )
                    ]
                )
            )
            
            operation = client.run_job(request=request)
            operations.append((config["name"], operation))
            print(f"✅ {config['description']} started successfully")
        
        print(f"✅ All {len(job_configs)} job instances started successfully.")
        return f"Successfully triggered {len(job_configs)} Cloud Run Job instances.", 200
        
    except Exception as e:
        print(f"❌ Failed to trigger jobs: {e}")
        traceback.print_exc()
        return "Error triggering jobs.", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))