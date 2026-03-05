from flask import Flask, request, jsonify, render_template_string
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
import io
import os
import threading

app = Flask(__name__)

# === CONFIGURATION (Global Settings) ===
JIRA_BASE = os.environ.get("JIRA_BASE")
PROJECT_KEY = os.environ.get("PROJECT_KEY", "SAM")
ISSUE_TYPE = os.environ.get("ISSUE_TYPE", "Task")

# === UI HTML (The Form) ===
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>Jira Bulk Upload Sandbox</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; background-color: #f4f5f7; }
        .box { max-width: 450px; background: white; padding: 25px; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        input, button { width: 100%; padding: 12px; margin: 10px 0; border-radius: 5px; border: 1px solid #ccc; box-sizing: border-box; }
        button { background-color: #0052cc; color: white; border: none; font-weight: bold; cursor: pointer; }
        button:hover { background-color: #0065ff; }
        .info { font-size: 12px; color: #666; }
    </style>
</head>
<body>
    <div class="box">
        <h2>Bulk Ticket Creator</h2>
        <form action="/process-csv" method="post" enctype="multipart/form-data">
            <input type="email" name="email" placeholder="Your Atlassian Email" required>
            <input type="password" name="token" placeholder="Your API Token" required>
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Upload & Create Tickets</button>
        </form>
        <p class="info">Tickets will be created as <b>Reporter: [Your Name]</b>.</p>
    </div>
</body>
</html>
"""

def create_tickets_task(df, user_email, user_token):
    """Function that runs in the background to create tickets"""
    user_auth = HTTPBasicAuth(user_email, user_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
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
        
        try:
            res = requests.post(f"{JIRA_BASE}/rest/api/3/issue", json=payload, auth=user_auth, headers=headers)
            if res.status_code == 201:
                print(f"SUCCESS: Created {res.json().get('key')}", flush=True)
            else:
                print(f"FAILED: Row {index+1} - {res.text}", flush=True)
        except Exception as e:
            print(f"CONNECTION ERROR: {str(e)}", flush=True)

@app.route("/", methods=["GET"])
def index():
    return render_template_string(HTML_UI)

@app.route("/process-csv", methods=["POST"])
def process_csv():
    try:
        # 1. Collect inputs from UI
        email = request.form.get("email")
        token = request.form.get("token")
        file = request.files.get("file")

        if not email or not token or not file:
            return "Error: Missing Email, Token, or File", 400

        # 2. Read the CSV data
        df = pd.read_csv(io.StringIO(file.stream.read().decode("UTF-8")))
        
        if len(df) == 0:
            return "Error: The CSV file is empty", 400

        # 3. Start Background Thread (so user doesn't wait and Render doesn't timeout)
        thread = threading.Thread(target=create_tickets_task, args=(df, email, token))
        thread.start()

        return f"<h3>Upload Successful!</h3><p>Processing {len(df)} rows. You can check Jira in a few moments.</p><a href='/'>Back</a>"

    except Exception as e:
        return f"Server Error: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
