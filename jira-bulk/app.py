from flask import Flask, request, jsonify
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
import io
import os

app = Flask(__name__)

# === CONFIGURATION (Use Environment Variables in Render) ===
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
        data = request.json

        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        issue_key = data.get("issueKey")
        attachment_url = data.get("attachmentUrl")

        if not issue_key or not attachment_url:
            return jsonify({"error": "Missing issueKey or attachmentUrl"}), 400

        # === Download Attachment ===
        file_response = requests.get(
            attachment_url,
            auth=auth,
            headers={"Accept": "application/json"}
        )

        if file_response.status_code != 200:
            return jsonify({
                "error": "Failed to download attachment",
                "status": file_response.status_code
            }), 400

        # === Read CSV ===
        csv_file = io.StringIO(file_response.text)

        try:
            df = pd.read_csv(csv_file)
        except Exception as e:
            return jsonify({"error": f"Invalid CSV format: {str(e)}"}), 400

        # Validate required column
        if "Summary" not in df.columns:
            return jsonify({"error": "CSV must contain 'Summary' column"}), 400

        created_issues = []
        errors = []

        # === Create Issues ===
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
                created_issues.append(response.json().get("key"))
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
        return jsonify({"error": f"Server error: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)