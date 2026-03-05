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

# === UI DESIGN  ===
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
            
            <label>Jira API Token</label>
            <input type="password" name="user_token" placeholder="Paste your personal token" required>
            
            <label>Upload CSV File</label>
            <input type="file" name="file" accept=".csv" required>
            
            <button type="submit">Create Tickets</button>
        </form>
    </div>
</body>
</html>
"""

# ================================
# 🔥 NEW — Get Jira accountId
# ================================
def get_account_id(email, auth, headers):
    try:
        url = f"{JIRA_BASE}/rest/api/3/user/search"
        params = {"query": email}

        res = requests.get(url, params=params, auth=auth, headers=headers)

        if res.status_code == 200 and res.json():
            return res.json()[0].get("accountId")
        else:
            print(f"WARNING: Could not find accountId for {email}", flush=True)
            return None

    except Exception as e:
        print(f"ERROR fetching accountId: {e}", flush=True)
        return None


# ================================
# 🚀 Background processor
# ================================
def process_in_background(df, user_email, user_token, reporter_name):
    auth = HTTPBasicAuth(user_email, user_token)
    headers = {"Accept": "application/json", "Content-Type": "application/json"}

    # ✅ Get reporter accountId once
    reporter_account_id = get_account_id(user_email, auth, headers)

    for index, row in df.iterrows():
        summary = str(row.get("Summary", "Site Access Request")).strip()
        if not summary or summary.lower() == "nan":
            continue

        fields_payload = {
            "project": {"key": PROJECT_KEY},
            "issuetype": {"name": ISSUE_TYPE},
            "summary": summary,
            "description": {
                "version": 1,
                "type": "doc",
                "content": [{
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": f"Requested by: {reporter_name}"
                    }]
                }]
            }
        }

        # ✅ Set reporter properly (fixes Anonymous)
        if reporter_account_id:
            fields_payload["reporter"] = {"id": reporter_account_id}

        payload = {"fields": fields_payload}

        try:
            res = requests.post(
                f"{JIRA_BASE}/rest/api/3/issue",
                json=payload,
                auth=auth,
                headers=headers
            )

            if res.status_code == 201:
                print(f"LOG: Created {res.json().get('key')} for {reporter_name}", flush=True)
            else:
                print(f"ERROR: Row {index+1} - {res.text}", flush=True)

        except Exception as e:
            print(f"CRITICAL ERROR: {str(e)}", flush=True)


# ================================
# 🌐 Routes
# ================================
@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML_UI)


@app.route("/process-csv", methods=["POST"])
def process_csv():
    rep_name = request.form.get("reporter_name")
    email = request.form.get("user_email")
    token = request.form.get("user_token")
    file = request.files.get("file")

    try:
        df = pd.read_csv(io.StringIO(file.stream.read().decode("UTF-8")))

        thread = threading.Thread(
            target=process_in_background,
            args=(df, email, token, rep_name)
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
# 🚀 Run App
# ================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
