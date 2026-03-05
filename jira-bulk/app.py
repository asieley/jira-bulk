from flask import Flask, request, render_template_string, send_from_directory
import requests
import pandas as pd
import io
import os
import threading

app = Flask(__name__)

# === CONFIGURATION ===
JIRA_BASE = os.environ.get("JIRA_BASE")
PROJECT_KEY = os.environ.get("PROJECT_KEY", "SAM")
ISSUE_TYPE = os.environ.get("ISSUE_TYPE", "Task")

# === UI DESIGN (Centered + Orange Button + Logo) ===
HTML_UI = """
<!DOCTYPE html>
<html>
<head>
    <title>Site Access Request</title>
    <style>
        body { 
            font-family: 'Segoe UI', sans-serif; 
            margin: 0; display: flex; justify-content: center; align-items: center; 
            height: 100vh; background-color: #f4f5f7; 
        }
        .container { 
            width: 100%; max-width: 450px; background: white; 
            padding: 40px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
            text-align: center;
        }
        img.logo { max-width: 120px; margin-bottom: 20px; }
        h2 { color: #172b4d; margin-bottom: 25px; font-size: 20px; }
        label { display: block; text-align: left; margin-bottom: 5px; font-weight: bold; color: #444; }
        input { 
            width: 100%; padding: 12px; margin-bottom: 20px; 
            border: 1px solid #dfe1e6; border-radius: 5px; box-sizing: border-box; 
        }
        button { 
            width: 100%; padding: 12px; background-color: #FF8C00; 
            color: white; border: none; border-radius: 5px; font-weight: bold; 
            cursor: pointer; font-size: 16px;
        }
        button:hover { background-color: #e67e00; }
    </style>
</head>
<body>
    <div class="container">
        <img src="/Logo.png" class="logo" alt="Company Logo">
        <h2>Site Access Request Bulk Upload of Tickets</h2>
        <form action="/process-csv" method="post" enctype="multipart/form-data">
            <label>Reporter Name</label>
            <input type="text" name="reporter_name" placeholder="Who is requesting this?" required>
            <label>Work Email</label>
            <input type="email" name="email" placeholder="email@company.com" required>
            <label>Upload CSV</label>
            <input type="file" name="file" accept=".csv" required>
            <button type="submit">Create Tickets</button>
        </form>
    </div>
</body>
</html>
"""

# === Success Page (with Back Button + Logo) ===
SUCCESS_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Tickets Processing</title>
    <style>
        body { 
            font-family: 'Segoe UI', sans-serif; 
            margin: 0; display: flex; justify-content: center; align-items: center; 
            height: 100vh; background-color: #f4f5f7; 
        }
        .container { 
            width: 100%; max-width: 450px; background: white; 
            padding: 40px; border-radius: 10px; box-shadow: 0 10px 25px rgba(0,0,0,0.1); 
            text-align: center;
        }
        img.logo { max-width: 120px; margin-bottom: 20px; }
        h3 { color: #172b4d; }
        button { 
            margin-top: 20px; padding: 10px 20px; background-color: #FF8C00; 
            color: white; border: none; border-radius: 5px; cursor: pointer;
            font-weight: bold; font-size: 14px;
        }
        button:hover { background-color: #e67e00; }
    </style>
</head>
<body>
    <div class="container">
        <img src="/Logo.png" class="logo" alt="Company Logo">
        <h3>Upload Received! Tickets are being created.</h3>
        <button onclick="window.location.href='/'">Back to Upload</button>
    </div>
</body>
</html>
"""

# === Ticket Processing Function ===
def process_in_background(df, reporter_name, reporter_email):
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    for index, row in df.iterrows():
        summary = str(row.get("Summary", "Site Access Request")).strip()
        user_type = str(row.get("User Type", "")).strip()
        access_start = str(row.get("Date", "")).strip()  # CSV column Date → Access Start
        
        if not summary or summary.lower() == "nan": 
            continue

        payload = {
            "fields": {
                "project": {"key": PROJECT_KEY},
                "issuetype": {"name": ISSUE_TYPE},
                "summary": summary,
                "description": {
                    "version": 1,
                    "type": "doc",
                    "content": [
                        {"type": "paragraph", 
                         "content": [{"type": "text", "text": f"Reporter: {reporter_name} | Email: {reporter_email}"}]}
                    ]
                },
                "customfield_10167": user_type,   # User Type
                "customfield_10164": access_start  # Access Start
            }
        }

        # For public project, no auth needed
        res = requests.post(f"{JIRA_BASE}/rest/api/3/issue", json=payload, headers=headers)

        if res.status_code == 201:
            print(f"LOG: Created {res.json().get('key')} for {reporter_name}", flush=True)
        else:
            print(f"ERROR: Failed to create ticket for {reporter_name} | Status: {res.status_code} | Response: {res.text}", flush=True)

# === Flask Routes ===
@app.route("/", methods=["GET"])
def home():
    return render_template_string(HTML_UI)

@app.route("/process-csv", methods=["POST"])
def process_csv():
    reporter_name = request.form.get("reporter_name")
    reporter_email = request.form.get("email")
    file = request.files.get("file")
    df = pd.read_csv(io.StringIO(file.stream.read().decode("UTF-8")))
    threading.Thread(target=process_in_background, args=(df, reporter_name, reporter_email)).start()
    return render_template_string(SUCCESS_PAGE)

# Serve Logo.png directly from repo root
@app.route("/Logo.png")
def serve_logo():
    return send_from_directory(os.getcwd(), "Logo.png")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
