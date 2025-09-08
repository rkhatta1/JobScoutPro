import os
import json
import base64
import traceback
import argparse
import time
from datetime import datetime
from google.cloud import secretmanager
from google.auth import default
import google.generativeai as genai
import gspread
from google.api_core import exceptions as gax_exceptions

# --- Configuration ---
GCP_PROJECT_ID = os.environ.get("GCLOUD_PROJECT")
GEMINI_API_KEY = None
RESUME_CONTENT = None
MAX_RATE_LIMIT_RETRIES = 3
RETRY_SLEEP_SECONDS = 60

def get_gemini_api_key():
    """Fetches the Gemini API key from Secret Manager."""
    global GEMINI_API_KEY
    if GEMINI_API_KEY: return GEMINI_API_KEY
        
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{GCP_PROJECT_ID}/secrets/gemini-api-key/versions/latest"
    response = client.access_secret_version(name=secret_name)
    GEMINI_API_KEY = response.payload.data.decode("UTF-8").strip()
    return GEMINI_API_KEY

def get_resume_content():
    """Fetches the resume content from Secret Manager."""
    global RESUME_CONTENT
    if RESUME_CONTENT: return RESUME_CONTENT
    
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{GCP_PROJECT_ID}/secrets/resume-latex/versions/latest"
    response = client.access_secret_version(name=secret_name)
    RESUME_CONTENT = response.payload.data.decode("UTF-8").strip()
    return RESUME_CONTENT

def get_sheet_id():
    """Fetches the Google Sheet ID from Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    secret_name = f"projects/{GCP_PROJECT_ID}/secrets/google-sheet-id/versions/latest"
    response = client.access_secret_version(name=secret_name)
    return response.payload.data.decode("UTF-8").strip()

def chunk_list(data, chunk_size):
    """Splits a list into smaller chunks of a specified size."""
    for i in range(0, len(data), chunk_size):
        yield data[i:i + chunk_size]

def is_rate_limit_error(exc: Exception) -> bool:
    """Detect 429/rate limit across common exception types/messages."""
    s = str(exc).lower()
    if isinstance(exc, (gax_exceptions.ResourceExhausted, gax_exceptions.TooManyRequests)):
        return True
    return ("429" in s) or ("rate limit" in s) or ("quota" in s) or ("exceeded" in s)

def deduplicate_by_url(matches):
    """Simple deduplication by URL within current batch"""
    seen_urls = set()
    unique_matches = []
    
    for job in matches:
        url = job.get("url", "").strip()
        if url not in seen_urls and url:
            seen_urls.add(url)
            unique_matches.append(job)
        else:
            print(f"🗑️ Duplicate URL in batch: {job.get('companyName')} - {job.get('positionName')}")
    
    print(f"🔍 Batch deduplication: {len(matches)} → {len(unique_matches)} jobs")
    return unique_matches

def check_against_existing_sheet_and_deduplicate(matches, sheet_id):
    """Remove duplicates both within the batch and against existing sheet entries"""
    
    # First, deduplicate within the current batch
    unique_matches = deduplicate_by_url(matches)
    
    if not unique_matches:
        return []
    
    # Then check against existing Google Sheet entries
    try:
        creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
        sa = gspread.authorize(creds)
        
        sheet = sa.open_by_key(sheet_id).worksheet("applications")
        
        # Get all existing URLs from the sheet (assuming URL is in column D)
        existing_data = sheet.get_all_values()
        if len(existing_data) > 1:  # Skip header row
            existing_urls = {row[3].strip() for row in existing_data[1:] if len(row) > 3 and row[3].strip()}
        else:
            existing_urls = set()
        
        print(f"📋 Found {len(existing_urls)} existing URLs in Google Sheet")
        
        # Filter out URLs that already exist in the sheet
        new_unique_matches = []
        for job in unique_matches:
            url = job.get("url", "").strip()
            if url not in existing_urls:
                new_unique_matches.append(job)
            else:
                print(f"🗑️ Already exists in sheet: {job.get('companyName')} - {job.get('positionName')}")
        
        print(f"🔍 Sheet deduplication: {len(unique_matches)} → {len(new_unique_matches)} jobs")
        return new_unique_matches
        
    except Exception as e:
        print(f"⚠️ Error checking against existing sheet: {e}")
        return unique_matches

 def analyze_job_batch(jobs_json):
    """Analyzes a batch of job data and returns good matches"""
    try:
        jobs_to_process = json.loads(jobs_json)
        
        if not jobs_to_process:
            print("Empty batch received.")
            return []

        print(f"🧠 AI Analyzer Job processing {len(jobs_to_process)} jobs.")
        
        resume_latex = get_resume_content()
        if not resume_latex:
            print("Could not load resume from secret.")
            return []

        api_key = get_gemini_api_key()
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        all_good_matches = []
        
        # Break jobs into smaller chunks of 5 (reduced for job reliability)
        job_chunks = list(chunk_list(jobs_to_process, 5))

        for i, chunk in enumerate(job_chunks):
            print(f"--- Processing Gemini chunk {i+1}/{len(job_chunks)} with {len(chunk)} jobs ---")
            
            
            prompt = f"""
            You are an expert AI job scout. Your task is to analyze a list of job postings against the provided resume and identify the best matches.

            MY RESUME (in LaTeX):
            ---
            {resume_latex}
            ---

            Jobs to analyze in this chunk:
            {json.dumps(chunk)}

            For each job in the list, you must visit the provided URL, read the full job description, and strictly evaluate it against my resume.
            Identify which of these jobs are a good match (a score of 40% or higher). A good match is a Software Engineer role for a new grad with less than 2 years of professional experience, and the required tech stack should align with the skills listed in my resume. **NO DATA ENGINEERING/MACHINE LEARNING/DATA ANALYST ROLES.** Also, importantly, the job description must NOT explicitly require US citizenship or permanent residency.

            Return a single JSON object with a key "good_matches". The value should be an array of the original job objects that you determine are a good match.

Assume the companyName and the positionName provided in the above mentioned jobs as truth. Do not replace them, only reply with the good matches from the bunch.

            If no jobs in the chunk are a good match, return an empty array for "good_matches". **Only reply with the JSON. Nothing else preceding it or following it.**

            Example response format:
            {{
                "good_matches": [
                    {{
                        "companyName": "TechCorp",
                        "positionName": "Junior Software Engineer",
                        "url": "https://xyz.com/job/12345"
                    }}
                ]
            }}
            """
          
            retries = 0
            while retries <= MAX_RATE_LIMIT_RETRIES:
                try:
                    response = model.generate_content(prompt)
                    cleaned_response = response.text.strip().replace("```json", "").replace("```", "")
                    
                    if not cleaned_response:
                        print(f"❌ Empty response from Gemini for chunk {i+1}")
                        break # Exit retry loop, move to next chunk
                        
                    analysis_result = json.loads(cleaned_response)
                    chunk_matches = analysis_result.get("good_matches", [])
                    
                    if chunk_matches:
                        print(f"✅ Gemini found {len(chunk_matches)} good matches in this chunk.")
                        all_good_matches.extend(chunk_matches)
                    else:
                        print("❌ Gemini: No good matches found in this chunk.")
                    
                    break # Success, exit retry loop

                except Exception as e:
                    if is_rate_limit_error(e):
                        retries += 1
                        if retries > MAX_RATE_LIMIT_RETRIES:
                            print(f"❌ Rate limit exceeded after {MAX_RATE_LIMIT_RETRIES} retries. Skipping chunk.")
                            break # Exit retry loop
                        print(f"⚠️ Rate limit hit. Waiting {RETRY_SLEEP_SECONDS}s... (Attempt {retries}/{MAX_RATE_LIMIT_RETRIES})")
                        time.sleep(RETRY_SLEEP_SECONDS)
                    else:
                        # It's a different error (e.g., JSONDecodeError, or another API error)
                        if isinstance(e, json.JSONDecodeError):
                             print(f"❌ JSON parse error for chunk {i+1}: {e}")
                             print(f"Response was: {response.text}")
                        else:
                             print(f"❌ Non-rate-limit error processing chunk {i+1}: {e}")
                        break # Exit retry loop on other errors

        return all_good_matches

    except Exception as e:
        print(f"❌ Fatal error in AI analysis: {e}")
        traceback.print_exc()
        return []

def main():
    parser = argparse.ArgumentParser(description='AI Job Analyzer')
    parser.add_argument('--jobs-json', required=True, help='JSON string of job data to analyze')
    parser.add_argument('--batch-id', default='unknown', help='Batch identifier for logging')
    
    args = parser.parse_args()
    
    print(f"🚀 Starting AI Analyzer Job (Batch: {args.batch_id})")
    
    # Analyze the jobs
    all_good_matches = analyze_job_batch(args.jobs_json)
    
    if all_good_matches:
        print(f"\n🔍 Found {len(all_good_matches)} matches. Processing deduplication...")
        
        sheet_id = get_sheet_id()
        unique_matches = check_against_existing_sheet_and_deduplicate(all_good_matches, sheet_id)
        
        if unique_matches:
            print(f"\n✅ After deduplication: {len(unique_matches)} unique jobs. Logging to Google Sheet...")
            
            creds, _ = default(scopes=["https://www.googleapis.com/auth/spreadsheets"])
            sa = gspread.authorize(creds)
            
            sheet = sa.open_by_key(sheet_id).worksheet("applications")
            
            rows_to_add = []
            for job in unique_matches:
                rows_to_add.append([
                    job.get("companyName"),
                    job.get("positionName"),
                    "applying",
                    job.get("url"),
                    datetime.now().strftime("%Y-%m-%d"),
                    "Scraped from JobRight, needs review."
                ])
            
            if rows_to_add:
                # Get the starting row number
                all_values = sheet.get_all_values()
                start_row = len(all_values) + 1
                end_row = start_row + len(unique_matches) - 1

                # Prepare data for columns A-D
                main_data = []
                date_notes_data = []

                for job in unique_matches:
                    main_data.append([
                        job.get("companyName"),
                        job.get("positionName"),
                        "applying", 
                        job.get("url")
                    ])

                    date_notes_data.append([
                        datetime.now().strftime("%Y-%m-%d"),
                        "Scraped from JobRight, needs review."
                    ])

                # Batch update - columns A-D
                sheet.update(f'A{start_row}:D{end_row}', main_data)

                # Batch update - columns F-G (skipping E for relevant contacts)
                sheet.update(f'F{start_row}:G{end_row}', date_notes_data)

                print(f"📝 Successfully logged {len(unique_matches)} unique jobs to Google Sheet.")
        else:
            print("\n❌ No unique matches remaining after deduplication.")
    else:
        print("\n❌ No good matches found in any chunks.")
    
    print(f"✅ AI Analyzer Job completed (Batch: {args.batch_id})")

if __name__ == "__main__":
    main()
