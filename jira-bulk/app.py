from flask import Flask, request, jsonify
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
import io
import os
import time

app = Flask(__name__)

# === CONFIGURATION ===
JIRA_BASE = os.environ.get("JIRA_BASE")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
PROJECT_KEY = os.environ.get("PROJECT_KEY", "SAM")
ISSUE_TYPE = os.environ.get("ISSUE_TYPE", "Task") 

auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}

@app.route("/", methods=["GET"])
def health_check():
    return "Server is running! Ready for Jira Webhooks.", 200

@app.route("/process-csv", methods=["POST", "GET"])
def process_csv():
    # If visited in a browser, return status instead of error
    if request.method == "GET":
        return "Endpoint is active. Please send a POST request via Jira Automation.", 200

    try:
        print("--- NEW REQUEST RECEIVED ---", flush=True)
        
        # Reduced sleep to 5 seconds to help avoid the 30s Jira timeout
        time.sleep(5) 

        data = request.get_json(silent=True)
        if not data:
            print("ERROR: No JSON data received.", flush=True)
            return jsonify({"error": "No data"}), 400

        issue_key = data.get("issueKey")
        attachment_url = data.get("attachmentUrl")

        if not issue_key or not attachment_url:
            print(f"ERROR: Missing data. Key: {issue_key}, URL: {attachment_url}", flush=True)
            return jsonify({"error": "Missing data"}), 400

        print(f"Processing CSV for trigger issue: {issue_key}", flush=True)
        
        # DOWNLOAD FILE
        file_response = requests.get(attachment_url, auth=auth)
        if file_response.status_code != 200:
            print(f"CRITICAL: Cannot access file. Status: {file_response.status_code}", flush=True)
            return jsonify({"error": "Access Denied to file"}), 403

        # READ CSV
        csv_file = io.StringIO(file_response.text)
        df = pd.read_csv(csv_file)
        row_count = len(df)
        print(f"SUCCESS: Found {row_count} rows in CSV.", flush=True)

        if row_count == 0:
            return jsonify({"status": "empty file"}), 200

        # CREATE ISSUES (Independent, no parent linking)
        created_count = 0
        for index, row in df.iterrows():
            summary = str(row.get("Summary", "")).strip()
            if not summary or summary.lower() == "nan": 
                continue

            payload = {
                "fields": {
                    "project": {"key": PROJECT_KEY},
                    "summary": summary,
                    "issuetype": {"name": ISSUE_TYPE}
                }
            }
            
            # Use API v3 for standard ticket creation
            res = requests.post(f"{JIRA_BASE}/rest/api/3/issue", json=payload, auth=auth, headers=headers)
            
            if res.status_code == 201:
                new_key = res.json().get("key")
                print(f"Created: {new_key}", flush=True)
                created_count += 1
            else:
                print(f"Failed row {index+1}: {res.text}", flush=True)

        print(f"FINISHED: Created {created_count} issues.", flush=True)
        return jsonify({"status": "done", "created": created_count}), 200

    except Exception as e:
        print(f"SERVER ERROR: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
