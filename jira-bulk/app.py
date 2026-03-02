from flask import Flask, request, jsonify
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
import io
import os
import threading
from datetime import datetime

app = Flask(__name__)

# === CONFIGURATION ===
JIRA_BASE = os.environ.get("JIRA_BASE")
JIRA_EMAIL = os.environ.get("JIRA_EMAIL")
JIRA_API_TOKEN = os.environ.get("JIRA_API_TOKEN")
PROJECT_KEY = os.environ.get("PROJECT_KEY", "FSAM")
ISSUE_TYPE = os.environ.get("ISSUE_TYPE", "Site Access Request")

auth = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
headers = {"Accept": "application/json", "Content-Type": "application/json"}

def to_adf(text):
    """Converts plain text to Atlassian Document Format (ADF)"""
    if not text or str(text).lower() == "nan":
        return None
    return {
        "version": 1,
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [
                    {
                        "type": "text",
                        "text": str(text)
                    }
                ]
            }
        ]
    }

def format_jira_date(date_val):
    try:
        if pd.isna(date_val) or str(date_val).lower() == "nan":
            return None
        dt = pd.to_datetime(date_val)
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")
    except:
        return None

def process_tickets_in_background(df):
    """Loop through CSV and create issues in the background"""
    created_count = 0
    for index, row in df.iterrows():
        work_activities = str(row.get("Work Activities", "Site Access Request")).strip()
        
        payload = {
            "fields": {
                "project": {"key": PROJECT_KEY},
                "issuetype": {"name": ISSUE_TYPE},
                "summary": work_activities,
                
                # Site ID (Dropdown)
                "customfield_10249": {"id": str(row.get("FTAP Site ID ID", "19987"))},
                
                # Asset Type (Text field)
                "customfield_10651": str(row.get("Asset Type", "")),
                
                # Maintenance Type (Dropdown)
                "customfield_10221": {"id": str(row.get("Maintenance Type ID", "19930"))},
                
                # Personnel Info
                "customfield_10255": str(row.get("Name", "")),
                "customfield_10241": {"id": str(row.get("Company ID", "19942"))},
                
                # ADF FIELDS (The fix for your error)
                "customfield_10227": to_adf(row.get("Contact Number")),
                "customfield_10254": to_adf(row.get("Personnel Names")),
                
                # Dates
                "customfield_10224": format_jira_date(row.get("Access Start")),
                "customfield_10225": format_jira_date(row.get("Access End"))
            }
        }
        
        # Remove None values
        payload["fields"] = {k: v for k, v in payload["fields"].items() if v is not None}

        res = requests.post(f"{JIRA_BASE}/rest/api/3/issue", json=payload, auth=auth, headers=headers)
        
        if res.status_code == 201:
            print(f"Row {index+1} success: {res.json().get('key')}", flush=True)
            created_count += 1
        else:
            print(f"Row {index+1} failed: {res.text}", flush=True)
    
    print(f"--- Finished Background Task: {created_count} tickets created ---", flush=True)

@app.route("/", methods=["GET"])
def home():
    return "Jira CSV Processor is running!", 200

@app.route("/process-csv", methods=["POST"])
def process_csv():
    try:
        print("--- NEW REQUEST RECEIVED ---", flush=True)
        data = request.json
        raw_attachment_url = data.get("attachmentUrl")

        if not raw_attachment_url:
            return jsonify({"error": "Missing URL"}), 400

        attachment_url = raw_attachment_url.split(",")[-1].strip()
        file_response = requests.get(attachment_url, auth=auth)
        
        if file_response.status_code != 200:
            return jsonify({"error": "Access Denied to file"}), 403

        # READ CSV
        df = pd.read_csv(io.StringIO(file_response.text))
        
        # Start the thread
        thread = threading.Thread(target=process_tickets_in_background, args=(df,))
        thread.start()

        # Respond to Jira immediately to prevent 30s timeout
        return jsonify({"status": "Accepted", "message": "Background processing started"}), 202

    except Exception as e:
        print(f"SERVER ERROR: {str(e)}", flush=True)
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
