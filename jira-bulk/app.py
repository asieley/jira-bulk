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

@app.route("/process-csv", methods=["POST"])
def process_csv():
    try:
        print("--- NEW REQUEST RECEIVED ---")
        time.sleep(10) # Wait for Jira upload to settle

        data = request.json
        issue_key = data.get("issueKey")
        attachment_url = data.get("attachmentUrl")

        if not issue_key or not attachment_url:
            print("ERROR: Missing data from Jira automation.")
            return jsonify({"error": "Missing data"}), 400

        print(f"Downloading file for issue: {issue_key}")
        
        # DOWNLOAD
        file_response = requests.get(attachment_url, auth=auth)
        
        # LOG THE DOWNLOAD STATUS
        print(f"Download status: {file_response.status_code}")
        
        if file_response.status_code != 200:
            print(f"CRITICAL: Cannot access file. Jira said: {file_response.text}")
            return jsonify({"error": "Access Denied to file"}), 403

        # READ CSV
        csv_file = io.StringIO(file_response.text)
        df = pd.read_csv(csv_file)
        
        row_count = len(df)
        print(f"SUCCESS: Found {row_count} rows in CSV.")

        if row_count == 0:
            print("WARNING: CSV is empty.")
            return jsonify({"status": "empty file"}), 200

        # CREATE ISSUES
        created_count = 0
        for index, row in df.iterrows():
            summary = str(row.get("Summary", "")).strip()
            if not summary or summary.lower() == "nan": continue

            payload = {
                "fields": {
                    "project": {"key": PROJECT_KEY},
                    "summary": f"Bulk: {summary}",
                    "issuetype": {"name": ISSUE_TYPE},
                    "parent": {"key": issue_key}
                }
            }
            res = requests.post(f"{JIRA_BASE}/rest/api/3/issue", json=payload, auth=auth, headers=headers)
            
            if res.status_code == 201:
                created_count += 1
            else:
                print(f"Failed row {index+1}: {res.text}")

        print(f"FINISHED: Created {created_count} issues.")
        return jsonify({"status": "done", "created": created_count}), 200

    except Exception as e:
        print(f"SERVER ERROR: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
