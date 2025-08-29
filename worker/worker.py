import os
import json
import base64
import threading
from flask import Flask, request
from scraper import JobRightScraper

app = Flask(__name__)

def run_scraping_task(start_index, end_index):
    """
    This function contains the actual scraping logic and will be run
    in a separate thread so it doesn't block the HTTP response.
    """
    print(f"BACKGROUND THREAD: Starting to process batch {start_index}-{end_index}")
    scraper = JobRightScraper()
    # The run_worker_task method handles the entire browser lifecycle
    collected_urls = scraper.run_worker_task(start_index, end_index)
    
    # TODO: In a full application, you would save these URLs to a database.
    print(f"BACKGROUND THREAD: Finished batch. Collected {len(collected_urls)} URLs.")
    print(f"--- URLs from batch {start_index}-{end_index} ---")
    for url in collected_urls:
        print(url)
    print("--- End of batch ---")


@app.route("/", methods=["POST"])
def process_batch():
    """
    Cloud Run entry point. Receives a Pub/Sub message, starts the scraping
    task in a background thread, and immediately returns a success response.
    """
    envelope = request.get_json()
    if not envelope or "message" not in envelope:
        return "Bad Request: invalid Pub/Sub message format", 400

    pubsub_message = envelope["message"]
    
    try:
        data_str = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        data = json.loads(data_str)
        start_index = data.get("start_index")
        end_index = data.get("end_index")

        if start_index is None or end_index is None:
            return "Bad Request: start_index or end_index missing", 400
            
        print(f"📦 Main thread: Received batch for jobs {start_index}-{end_index}.")
        
        # --- START OF FIX: RUN IN BACKGROUND ---
        # Create and start a background thread to do the heavy lifting
        background_thread = threading.Thread(
            target=run_scraping_task,
            args=(start_index, end_index)
        )
        background_thread.start()
        # --- END OF FIX ---
        
        print(f"✅ Main thread: Acknowledged message. Task is running in background.")
        # Return an immediate 200 OK to Pub/Sub to prevent retries
        return "Successfully acknowledged and started processing batch.", 200

    except Exception as e:
        print(f"❌ Main thread: Failed to start background task: {e}")
        return "Error starting batch processing.", 500

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT, debug=True)