from flask import Flask, request, render_template_string
import requests
import pandas as pd
from requests.auth import HTTPBasicAuth
import io
import os
import threading

app = Flask(__name__)

# ================================
# 🔧 CONFIG
# ================================
JIRA_BASE = os.environ.get("JIRA_BASE")
SERVICE_DESK_ID = os.environ.get("SERVICE_DESK_ID")
REQUEST_TYPE_ID = os.environ.get("REQUEST_TYPE_ID")
# ✅ Single server agent credentials
JIRA_AGENT_EMAIL = os.environ.get("JIRA_AGENT_EMAIL")
JIRA_AGENT_TOKEN = os.environ.get("JIRA_AGENT_TOKEN")

# ================================
# 🎨 UI (REMOVE TOKEN INPUT)
# ================================
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>Site Access Request</title>
    <style>
        body { 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
            margin: 0; display: flex; justify-content: center; align-items: center; 
            height: 100vh; background-color: #f4f5f7; 
        }
        .container { 
            width: 100%; max-width: 450px; background: white; 
            padding: 40px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
            text-align: center;
        }
        h2 { color: #172b4d; margin-bottom: 25px; font-size: 20px; line-height: 1.4; }
        label { display: block; text-align: left; margin-bottom: 5px; font-weight: bold; color: #444; }
        input { 
            width: 100%; padding: 12px; margin-bottom: 20px; 
            border: 1px solid #dfe1e6; border-radius: 5px; box-sizing: border-box; font-size: 14px;
        }
        button { 
            width: 100%; padding: 12px; background-color: #FF8C00;
            color: white; border: none; border-radius: 5px; font-weight: bold; 
            cursor: pointer; font-size: 16px; transition: background 0.3s;
        }
        button:hover { background-color: #e67e00; }
        .footer-text { font-size: 12px; color: #6b778c; margin-top: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <h2>Site Access Request Bulk Upload of Tickets</h2>
        <form action="/process-csv" method="post" enctype="multipart/form-data">
            <label>Reporter Name</label>
            <input type="text" name="reporter_name" placeholder="Enter your full name" required>

            <label>Work Email</label>
            <input type="email" name="user_email" placeholder="yourname@company.com" required>
            
            <label>Upload CSV File</label>
            <input type="file" name="file" accept=".csv" required>
            
            <button type="submit">Create Tickets</button>
        </form>
    </div>
</body>
</html>
"""

# ================================
# 🚀 BACKGROUND PROCESSOR (SINGLE AGENT)
# ================================
def process_in_background(df, user_email, reporter_name):
    auth = HTTPBasicAuth(JIRA_AGENT_EMAIL, JIRA_AGENT_TOKEN)

    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-ExperimentalApi": "opt-in"
    }

    for index, row in df.iterrows():
        summary = str(row.get("Summary", "Site Access Request")).strip()
        if not summary or summary.lower() == "nan":
            continue

        payload = {
            "serviceDeskId": SERVICE_DESK_ID,
            "requestTypeId": REQUEST_TYPE_ID,
            "raiseOnBehalfOf": user_email,  # ✅ Correct reporter
            "requestFieldValues": {
                "summary": summary,
                "description": f"Requested by: {reporter_name}"
            }
        }

        try:
            res = requests.post(
                f"{JIRA_BASE}/rest/servicedeskapi/request",
                json=payload,
                auth=auth,
                headers=headers
            )

            if res.status_code in (200, 201):
                key = res.json().get("issueKey")
                print(f"LOG: Created {key} for {reporter_name}", flush=True)
            else:
                print(f"ERROR Row {index+1}: {res.status_code} - {res.text}", flush=True)

        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}", flush=True)

# ================================
# 🌐 ROUTES
# ================================
@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML_UI)

@app.route("/process-csv", methods=["POST"])
def process_csv():
    rep_name = request.form.get("reporter_name")
    email = request.form.get("user_email")
    file = request.files.get("file")

    try:
        df = pd.read_csv(io.StringIO(file.stream.read().decode("UTF-8")))

        thread = threading.Thread(
            target=process_in_background,
            args=(df, email, rep_name)
        )
        thread.start()

        return f"""
        <div style='text-align:center; padding-top: 50px; font-family: Segoe UI;'>
            <h2>Processing Started!</h2>
            <p>Creating {len(df)} tickets for {rep_name}.</p>
            <a href='/'>Back</a>
        </div>
        """

    except Exception as e:
        return f"Error: {str(e)}", 500

# ================================
# 🚀 RUN
# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
