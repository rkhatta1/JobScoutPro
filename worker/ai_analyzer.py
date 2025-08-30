import os
import json
import base64
import traceback
from datetime import datetime
from flask import Flask, request
from google.cloud import secretmanager
import google.generativeai as genai
import gspread

app = Flask(__name__)

# --- Configuration ---
GCP_PROJECT_ID = os.environ.get("GCLOUD_PROJECT")
SHEET_ID = os.environ.get("SHEET_ID")
GEMINI_API_KEY = None
RESUME_CONTENT = None

def get_gemini_api_key():
    """Fetches the Gemini API key from Secret Manager."""
    global GEMINI_API_KEY
    if GEMINI_API_KEY: return GEMINI_API_KEY
        
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{GCP_PROJECT_ID}/secrets/gemini-api-key/versions/latest"
    response = client.access_secret_version(name=secret_name)
    GEMINI_API_KEY = response.payload.data.decode("UTF-8")
    return GEMINI_API_KEY

def get_resume_content():
    """Reads the resume content from the secret file path."""
    global RESUME_CONTENT
    if RESUME_CONTENT: return RESUME_CONTENT
    
    resume_path = "/run/secrets/RESUME_LATEX"
    if os.path.exists(resume_path):
        with open(resume_path, "r") as f:
            RESUME_CONTENT = f.read()
        return RESUME_CONTENT
    else:
        print("⚠️ Resume secret file not found.")
        return None

def chunk_list(data, chunk_size):
    """Splits a list into smaller chunks of a specified size."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

@app.route("/", methods=["POST"])
def analyze_job_batch():
    """Receives a large batch of URLs, breaks it into smaller chunks for Gemini,
    analyzes them, and logs all good matches to Sheets."""
    envelope = request.get_json()
    if not envelope or "message" not in envelope:
        return "Bad Request", 400

    pubsub_message = envelope["message"]
    try:
        data_str = base64.b64decode(pubsub_message["data"]).decode("utf-8")
        data = json.loads(data_str)
        urls_to_process = data.get("urls", [])
        
        if not urls_to_process:
            return "Empty batch received.", 200

        print(f"🧠 AI Analyzer received a large batch of {len(urls_to_process)} URLs.")
        
        resume_latex = get_resume_content()
        if not resume_latex:
            return "Could not load resume from secret.", 500

        api_key = get_gemini_api_key()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        all_good_matches = []
        
        # --- START OF GEMINI BATCHING FIX ---
        # Break the 75 URLs into smaller chunks of 15
        url_chunks = list(chunk_list(urls_to_process, 15))

        for i, chunk in enumerate(url_chunks):
            print(f"--- Processing Gemini chunk {i+1}/{len(url_chunks)} with {len(chunk)} URLs ---")
            
            prompt = f"""
            You are an expert AI job scout. Your task is to analyze a list of job application URLs against the provided resume and identify the best matches.

            MY RESUME (in LaTeX):
            ---
            {resume_latex}
            ---

            URLs to analyze in this chunk:
            {json.dumps(chunk)}

            For each URL, you must visit the page, read the job description, and strictly evaluate it against my resume.
            Identify which of these jobs are a good match (a score of 40% or higher). A good match is a Software Engineer role for a new grad with less than 2 years of professional experience, and the required tech stack should align with the skills listed in my resume. Also, importantly, the job description must NOT explicitly require US citizenship or permanent residency.

            Return a single JSON object with a key "good_matches". The value should be an array of objects. Each object in the array represents a good match and must have the keys "companyName", "positionName", and "url".

            If no jobs are a good match, return an empty array for "good_matches".

            Example response format:
            {{
                "good_matches": [
                    {{
                        "companyName": "TechCorp",
                        "positionName": "Junior Software Engineer",
                        "url": "https://xyz.com/job/12345"
                    }},
                    {{
                        "companyName": "InnovateX",
                        "positionName": "Software Developer",
                        "url": "https://xyz.com/job/67890"
                    }}
                ]
            }}
            """
            
            response = model.generate_content(prompt)
            cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
            analysis_result = json.loads(cleaned_response)
            
            chunk_matches = analysis_result.get("good_matches", [])
            if chunk_matches:
                print(f"✅ Gemini found {len(chunk_matches)} good matches in this chunk.")
                all_good_matches.extend(chunk_matches)
            else:
                print("❌ Gemini: No good matches found in this chunk.")
        # --- END OF GEMINI BATCHING FIX ---

        if all_good_matches:
            print(f"\n✅ All chunks processed. Total good matches found: {len(all_good_matches)}. Logging to Google Sheet...")
            
            sa = gspread.service_account()
            sheet = sa.open_by_key(SHEET_ID).worksheet("applications")
            
            rows_to_add = []
            for job in all_good_matches:
                rows_to_add.append([
                    job.get("companyName"),
                    job.get("positionName"),
                    "Applying",
                    job.get("url"),
                    "", 
                    datetime.now().strftime("%Y-%m-%d"),
                    "Scraped from JobRight, needs review."
                ])
            
            if rows_to_add:
                sheet.append_rows(rows_to_add)
                print(f"📝 Successfully logged {len(rows_to_add)} jobs to Google Sheet.")
        else:
            print("\n❌ All chunks processed. No good matches found in the entire batch.")

        return "Successfully analyzed all chunks in the batch.", 200

    except Exception as e:
        print(f"❌ Worker failed to process batch. Error: {e}")
        traceback.print_exc()
        return "Error processing batch.", 200