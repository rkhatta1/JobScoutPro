import os
import json
import time
import traceback
from flask import Flask
from google.cloud import pubsub_v1
from dotenv import load_dotenv
from scraper import JobRightScraper

load_dotenv()

app = Flask(__name__)

@app.route("/", methods=["GET"])
def dispatch_jobs():
    """Cloud Run entry point with enhanced debugging."""
    
    # --- START OF DEBUGGING BLOCK ---
    print("--- DUMPING ALL ENVIRONMENT VARIABLES ---")
    for key, value in os.environ.items():
        print(f"{key}: {value}")
    print("--- END OF ENV DUMP ---")
    
    PROJECT_ID = os.environ.get("GCLOUD_PROJECT")
    
    # This debug line is crucial - it will tell us what value is being read.
    print(f"DEBUG: The Project ID was read as: '{PROJECT_ID}'")
    # --- END OF DEBUGGING BLOCK ---
    
    TOPIC_ID = "job-batches"
    
    if not PROJECT_ID:
        print("❌ CRITICAL: GCLOUD_PROJECT environment variable not found or is empty.")
        return "Internal configuration error: Project ID not found.", 500
    
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(PROJECT_ID, TOPIC_ID)
    
    scraper = JobRightScraper()
    try:
        if not scraper.setup_driver():
            return "Failed to setup driver", 500
        
        email = os.environ.get("JOBRIGHT_EMAIL")
        password = os.environ.get("JOBRIGHT_PASSWORD")

        if not scraper.login(email, password) or not scraper.switch_to_most_recent():
            return "Login or setup failed", 500

        total_jobs_found = scraper.load_jobs(150)
        print(f"✅ Dispatcher: Found {total_jobs_found} total jobs.")
        
        num_workers = 2
        batch_size = (total_jobs_found + num_workers - 1) // num_workers
        print(f"✅ Dispatcher: Splitting work for {num_workers} workers.")

        for i in range(num_workers):
            start_index = i * batch_size
            end_index = min(start_index + batch_size, total_jobs_found)
            
            if start_index >= end_index: continue

            message_data = {"start_index": start_index, "end_index": end_index}
            message_future = publisher.publish(topic_path, data=json.dumps(message_data).encode("utf-8"))
            message_future.result()
            print(f"🚀 Dispatched batch for jobs {start_index}-{end_index}")
        
        return f"Successfully dispatched {num_workers} batches.", 200

    except Exception as e:
        print(f"❌ Dispatcher failed: {e}")
        traceback.print_exc()
        return "An internal error occurred", 500
    finally:
        if scraper.driver:
            scraper.driver.quit()

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT, debug=True)