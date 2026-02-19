from flask import Flask, request, jsonify
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
import io
import os
import time  # NEW: For the delay

app = Flask(__name__)

# === CONFIGURATION ===
JIRA_BASE = os.environ.get("JIRA_BASE")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
PROJECT_KEY = os.environ.get("PROJECT_KEY", "SAM")
ISSUE_TYPE = os.environ.get("ISSUE_TYPE", "Task")

auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)

headers = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

@app.route("/process-csv", methods=["POST"])
def process_csv():
    try:
        # 1. WAIT FOR JIRA (The "Race Condition" Fix)
        # Since Jira has no "Wait" action, we pause here for 10 seconds 
        # to ensure the file is ready for download.
        print("Request received. Sleeping for 10 seconds to allow Jira upload...")
        time.sleep(10)

        data = request.json
        if not data:
            print("Error: Missing JSON body")
            return jsonify({"error": "Missing JSON body"}), 400

        issue_key = data.get("issueKey")
        attachment_url = data.get("attachmentUrl")

        print(f"Processing Issue: {issue_key}")
        print(f"Attachment URL: {attachment_url}")

        if not issue_key or not attachment_url:
            return jsonify({"error": "Missing issueKey or attachmentUrl"}), 400

        # 2. DOWNLOAD ATTACHMENT
        file_response = requests.get(
            attachment_url,
            auth=auth,
            headers={"Accept": "application/json"}
        )

        if file_response.status_code != 200:
            print(f"Failed to download. Status: {file_response.status_code}")
            return jsonify({
                "error": "Failed to download attachment. Check permissions.",
                "status": file_response.status_code
            }), 400

        # 3. READ CSV
        csv_file = io.StringIO(file_response.text)
        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            return jsonify({"error": f"Invalid CSV format: {str(e)}"}), 400

        if "Summary" not in df.columns:
            return jsonify({"error": "CSV must contain 'Summary' column"}), 400

        created_issues = []
        errors = []

        # 4. CREATE ISSUES
        for index, row in df.iterrows():
            summary_value = str(row["Summary"]).strip()

            if not summary_value or summary_value.lower() == "nan":
                continue

            payload = {
                "fields": {
                    "project": {"key": PROJECT_KEY},
                    "summary": f"Bulk Request: {summary_value}",
                    "issuetype": {"name": ISSUE_TYPE},
                    "parent": {"key": issue_key}
                }
            }

            response = requests.post(
                f"{JIRA_BASE}/rest/api/3/issue",
                json=payload,
                auth=auth,
                headers=headers
            )

            if response.status_code == 201:
                new_key = response.json().get("key")
                created_issues.append(new_key)
                print(f"Created: {new_key}")
            else:
                errors.append({
                    "row": index + 1,
                    "error": response.text
                })

        return jsonify({
            "status": "completed",
            "created_count": len(created_issues),
            "created_issues": created_issues,
            "errors": errors
        })

    except Exception as e:
        print(f"Server Error: {str(e)}")
        return jsonify({"error": f"Server error: {str(e)}"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000) # Render uses port 10000 by default
