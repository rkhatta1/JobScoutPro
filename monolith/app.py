import os
from flask import Flask
from scraper import JobRightScraper

app = Flask(__name__)

@app.route("/", methods=["GET"])
def run_scraper_job():
    """
    Entry point triggered by Cloud Scheduler. Runs the entire scraping process.
    """
    scraper = JobRightScraper()
    collected_urls = scraper.run()
    
    if collected_urls:
        print(f"\n--- COLLECTED URLS ({len(collected_urls)}) ---")
        for i, url in enumerate(collected_urls, 1):
            print(f"{i:2d}. {url}")
        return f"Scraping complete. Collected {len(collected_urls)} URLs.", 200
    else:
        print("No URLs were collected.")
        return "Scraping ran, but no URLs were collected.", 200

if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=PORT, debug=True)