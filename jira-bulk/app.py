from flask import Flask, request, render_template_string
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

# === UI DESIGN (Centered & Clean) ===
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>Jira Bulk Upload</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; 
            display: flex; 
            justify-content: center; 
            align-items: center; 
            height: 100vh; 
            background-color: #f4f5f7; 
        }
        .container { 
            width: 100%; 
            max-width: 400px; 
            background: white; 
            padding: 40px; 
            border-radius: 10px; 
            box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
            text-align: center;
        }
        h2 { color: #172b4d; margin-bottom: 25px; }
        label { display: block; text-align: left; margin-bottom: 5px; font-weight: bold; color: #444; }
        input { 
            width: 100%; 
            padding: 12px; 
            margin-bottom: 20px; 
            border: 1px solid #dfe1e6; 
            border-radius: 5px; 
            box-sizing: border-box; 
            font-size: 14px;
        }
        button { 
            width: 100%; 
            padding: 12px; 
            background-color: #0052cc; 
            color: white; 
            border: none; 
            border-radius: 5px; 
            font-weight: bold; 
            cursor: pointer; 
            font-size: 16px;
            transition: background 0.3s;
        }
        button:hover { background-color: #0065ff; }
        .footer-text { font-size: 12px; color: #6b778c; margin-top: 20px; line-height: 1.5; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Bulk Ticket Uploader</h2>
        <form action="/process-csv" method="post" enctype="multipart/form-data">
            <label>Work Email</label>
            <input type="email" name="user_email" placeholder="email@company.com" required>
            
            <label>Jira API Token</label>
            <input type="password" name="user_token" placeholder="Paste your API token" required>
            
            <label>Upload CSV</label>
            <input type="file" name="file" accept=".csv" required>
            
            <button type="submit">Create Tickets</button>
        </form>
        <div class="footer-text">
            Tickets will reflect <b>your name</b> as the Reporter in Jira.
        </div>
    </div>
</body>
</html>
"""

def process_in_background(df, user_email, user_token):
    auth = HTTPBasicAuth(user_email, user_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    for index, row in df.iterrows():
        summary = str(row.get("Summary", "Bulk Task")).strip()
        if not summary or summary.lower() == "nan": continue

        payload = {
            "fields": {
                "project": {"key": PROJECT_KEY},
                "issuetype": {"name": ISSUE_TYPE},
                "summary": summary
            }
        }
        # Using API v3 to ensure proper Reporter attribution
        requests.post(f"{JIRA_BASE}/rest/api/3/issue", json=payload, auth=auth, headers=headers)

@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML_UI)

@app.route("/process-csv", methods=["POST"])
def process_csv():
    email = request.form.get("user_email")
    token = request.form.get("user_token")
    file = request.files.get("file")

    if not email or not token or not file:
        return "Missing required information", 400

    try:
        df = pd.read_csv(io.StringIO(file.stream.read().decode("UTF-8")))
        thread = threading.Thread(target=process_in_background, args=(df, email, token))
        thread.start()
        return f"<div style='text-align:center; padding-top: 50px;'><h2>Success!</h2><p>Processing {len(df)} tickets for {email}.</p><a href='/'>Back</a></div>"
    except Exception as e:
        return f"Error: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
