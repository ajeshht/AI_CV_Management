from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import os
import re
import io
import requests
import pdfplumber
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from dotenv import load_dotenv

app = Flask(__name__)

load_dotenv()

# --- GOOGLE SHEET CONFIG ---
SHEET_ID = os.getenv("SHEET_ID")  # Replace with your Google Sheet ID
RANGE = "Sheet1!A:D"
SERVICE_ACCOUNT_FILE = "credentials.json"

# Authenticate Google Sheets API
creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
])
service = build("sheets", "v4", credentials=creds)


#text parser function
def extract_info(text):
    name = re.findall(r"Name[:\-]?\s*(.*)([A-Za-z\s]+)", text)
    email = re.findall(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+", text)
    phone = re.findall(r"\+?\d[\d\s-]{8,15}", text)
    skills = re.findall(r"Skills[:\-]?\s*(.*)([A-Za-z,\s]+)", text)

    return {
        "Name": name[0].strip() if name else "N/A",
        "Email": email[0] if email else "N/A",
        "Phone": phone[0] if phone else "N/A",
        "Skills": skills[0].strip() if skills else "N/A"
    }




# --- EXTRACT TEXT FROM PDF ---
def extract_text_from_pdf(file_bytes):
    text = ""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text += page.extract_text() + "\n"
    return text


# --- GOOGLE SHEETS APPEND ---
def save_to_sheet(data):
    row = [[data["Name"], data["Email"], data["Phone"], data["Skills"]]]
    service.spreadsheets().values().append(
        spreadsheetId=SHEET_ID,
        range=RANGE,
        valueInputOption="RAW",
        body={"values": row}
    ).execute()


# --- WHATSAPP WEBHOOK ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    msg = request.form.get("Body", "")
    media_url = request.form.get("MediaUrl0", "")
    response = MessagingResponse()

    if media_url:
        response.message("📄 Resume received. Processing...")
        file_data = requests.get(media_url).content
        text = extract_text_from_pdf(file_data)
    else:
        text = msg

    data = extract_info(text)
    save_to_sheet(data)

    reply = f"Data saved to Google Sheet:\nName: {data['Name']}\nEmail: {data['Email']}\nPhone: {data['Phone']}"
    response.message(reply)

    return str(response)




if __name__ == "__main__":
    app.run(port=5000, debug=True)
