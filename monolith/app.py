import os
import json
import threading
from flask import Flask
from scraper import JobRightScraper
from google.cloud import pubsub_v1

app = Flask(__name__)

GCP_PROJECT_ID = os.environ.get("GCLOUD_PROJECT")
TOPIC_ID = "scraped-urls"

def chunk_list(data, num_chunks):
    """Splits a list into a specified number of chunks."""
    k, m = divmod(len(data), num_chunks)
    return [data[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(num_chunks)]

def run_background_scraping():
    """
    This function runs the entire scraping and publishing workflow
    in a background thread.
    """
    print("BACKGROUND THREAD: Starting collector task...")
    scraper = JobRightScraper()
    collected_urls = scraper.run()
    
    if collected_urls:
        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(GCP_PROJECT_ID, TOPIC_ID)
        
        num_batches = 2 # Based on worker's max-instances
        url_batches = chunk_list(list(set(collected_urls)), num_batches)
        
        print(f"BACKGROUND THREAD: Publishing {len(collected_urls)} URLs in {num_batches} batches...")
        
        for i, batch in enumerate(url_batches):
            if not batch: continue
            message_data = {"urls": batch}
            publisher.publish(topic_path, data=json.dumps(message_data).encode("utf-8"))
            print(f"BACKGROUND THREAD: 🚀 Dispatched batch #{i+1} with {len(batch)} URLs.")
            
        print("BACKGROUND THREAD: ✅ All URLs published successfully.")
    else:
        print("BACKGROUND THREAD: No URLs were collected.")

@app.route("/", methods=["GET"])
def run_scraper_job():
    """
    Entry point triggered by Cloud Scheduler. Acknowledges the request
    and starts the scraping process in a background thread.
    """
    print("✅ Main thread: Received trigger from Cloud Scheduler.")
    
    # Create and start the background thread
    background_thread = threading.Thread(target=run_background_scraping)
    background_thread.start()
    
    print("✅ Main thread: Acknowledged request. Collector is now running in the background.")
    # Immediately return a success response to the scheduler
    return "Successfully triggered the collector service.", 200

# The __main__ block is only for local testing, not used in Cloud Run
if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT, debug=True)