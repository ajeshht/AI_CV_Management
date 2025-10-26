from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import requests
import io
import pdfplumber
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
import google.generativeai as genai
import os
import json
import re
from dotenv import load_dotenv

load_dotenv() 

app = Flask(__name__)

# GOOGLE SHEET CONFIG

SHEET_ID = os.environ.get("SHEET_ID", "your_sheet_id_here")
SERVICE_ACCOUNT_FILE = os.environ.get("SERVICE_ACCOUNT_FILE", "credentials.json")


creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
])
service = build("sheets", "v4", credentials=creds)

# Gemini ai setup
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    try:
        with open("gemini_key.txt", "r") as f:
            GEMINI_API_KEY = f.read().strip()
    except:
        print("Warning: GEMINI_API_KEY not found")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    print("Gemini AI configured successfully")

# --- TWILIO AUTHENTICATION SETUP ---
# Get Twilio credentials from environment variables
TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
    try:
        # Try to load from file
        with open("twilio_credentials.json", "r") as f:
            twilio_creds = json.load(f)
            TWILIO_ACCOUNT_SID = twilio_creds.get("account_sid")
            TWILIO_AUTH_TOKEN = twilio_creds.get("auth_token")
    except:
        print("Twilio credentials not found. Media download may fail.")

if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    print("Twilio credentials configured")
else:
    print("Twilio credentials missing - media download will fail")

# --- IMPROVED PHONE NUMBER REGEX PATTERNS ---
def extract_phone_number(text):
    """Extract phone number from text using multiple regex patterns"""
    patterns = [
        r'\+?\d{1,3}[-.\s]?\(?\d{1,4}\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}',
        r'[789]\d{1,4}[-.\s]?\d{1,5}[-.\s]?\d{1,5}',
        r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
        r'\b\d{10}\b',
        r'\d{3}[-.\s]?\d{3}[-.\s]?\d{4}',
        r'(\+91|91|0)?[-.\s]?[789]\d{2}[-.\s]?\d{3}[-.\s]?\d{4}'
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text)
        if matches:
            phone = matches[0]
            if isinstance(phone, tuple):
                phone = ''.join(phone)
            
            phone = re.sub(r'[^\d+]', '', phone)
            
            if phone.startswith('91') and len(phone) == 12:
                phone = '+' + phone
            elif len(phone) == 10 and phone[0] in '789':
                phone = '+91' + phone
            elif len(phone) == 11 and phone.startswith('0'):
                phone = '+91' + phone[1:]
            
            print(f"Extracted phone: {phone}")
            return phone
    
    return "N/A"

# --- EXTRACT TEXT FROM PDF ---
def extract_text_from_pdf(file_bytes):
    """Extract text from PDF with robust error handling"""
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text += f"{page_text}\n"
                except Exception as page_error:
                    print(f"Error extracting text from page {page_num + 1}: {page_error}")
                    continue
    except Exception as e:
        print(f"PDF extraction error: {e}")
        return ""
    
    return text

# --- DOWNLOAD MEDIA FROM TWILIO WITH AUTHENTICATION ---
def download_twilio_media(media_url):
    """Download media from Twilio with proper authentication"""
    try:
        print(f"Downloading media from: {media_url}")
        
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            print(" Twilio credentials missing - cannot download media")
            return None, "no_credentials"
        
        # Method 1: Using requests with basic auth (recommended)
        response = requests.get(
            media_url,
            auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
            timeout=30
        )
        
        print(f" Response status: {response.status_code}")
        print(f"Content-Type: {response.headers.get('Content-Type', 'Unknown')}")
        print(f"Content-Length: {len(response.content)} bytes")
        
        if response.status_code == 401:
            print("Authentication failed - check Twilio credentials")
            return None, "auth_failed"
        elif response.status_code == 404:
            print(" Media not found - URL might be expired")
            return None, "not_found"
        elif response.status_code != 200:
            print(f"Download failed with status: {response.status_code}")
            return None, "download_failed"
        
        content = response.content
        
        # Check if it's an XML error response
        content_type = response.headers.get('Content-Type', '').lower()
        if 'xml' in content_type:
            print("Received XML response instead of media file")
            try:
                # Try to parse XML error message
                import xml.etree.ElementTree as ET
                root = ET.fromstring(content.decode('utf-8'))
                error_msg = "Unknown Twilio error"
                for elem in root.iter():
                    if elem.text and 'error' in elem.tag.lower():
                        error_msg = elem.text
                        break
                print(f" Twilio error: {error_msg}")
            except:
                print("Could not parse XML error response")
            return None, "xml_error"
        
        # Check if content is too small to be a valid file
        if len(content) < 100:
            print(f" File too small ({len(content)} bytes), likely not a valid media file")
            return None, "file_too_small"
        
        # Check if it's a valid PDF
        if content.startswith(b'%PDF'):
            print("Valid PDF file downloaded")
        else:
            print("Downloaded file may not be a valid PDF")
        
        return content, "success"
        
    except requests.exceptions.Timeout:
        print("Download timeout - media URL might be invalid")
        return None, "timeout"
    except Exception as e:
        print(f"Error downloading media: {e}")
        return None, "exception"

# --- DETECT FILE TYPE ---
def detect_file_type(file_bytes):
    """Simple file type detection based on content"""
    if len(file_bytes) < 4:
        return "unknown"
    
    if file_bytes.startswith(b'%PDF'):
        return 'application/pdf'
    
    return 'application/octet-stream'

# --- RESUME PARSING ---
def parse_resume_with_gemini(text):
    if not GEMINI_API_KEY or not text.strip():
        return parse_resume_simple(text)
    
    try:
        model = genai.GenerativeModel('gemini-1.0-pro')
        
        prompt = """
        Extract the following information from the resume text:
        
        1. **Name**: Full name of the person
        2. **Email**: Email address
        3. **Phone**: Phone number (include country code if available)
        4. **Skills**: Technical and professional skills (comma-separated)
        
        Return ONLY valid JSON format:
        {
            "Name": "extracted name or N/A",
            "Email": "extracted email or N/A", 
            "Phone": "extracted phone number or N/A",
            "Skills": "comma-separated skills or N/A"
        }
        
        Resume Text:
        """ + text[:8000]
        
        response = model.generate_content(prompt)
        result_text = response.text.strip()
        
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(result_text)
        
        # If Gemini returns N/A for phone, try our regex as fallback
        if data.get("Phone") == "N/A" or not data.get("Phone"):
            extracted_phone = extract_phone_number(text)
            data["Phone"] = extracted_phone
        
        print(f"Parsed data: {data}")
        return data
        
    except Exception as e:
        print(f"Gemini AI error: {e}")
        return parse_resume_simple(text)

def parse_resume_simple(text):
    if not text.strip():
        return {"Name": "N/A", "Email": "N/A", "Phone": "N/A", "Skills": "N/A"}
    
    print("Using simple parser for text extraction")
    
    # Extract email
    email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
    emails = re.findall(email_pattern, text)
    email = emails[0] if emails else "N/A"
    print(f"📧 Extracted email: {email}")
    
    # Extract phone
    phone = extract_phone_number(text)
    
    # Extract name
    lines = text.split('\n')
    name = "N/A"
    contact_keywords = ['email', 'phone', 'mobile', 'contact', 'resume', 'cv', 'linkedin', 'github']
    
    for line in lines[:15]:
        line = line.strip()
        if line and len(line) <= 50:
            if any(keyword in line.lower() for keyword in contact_keywords):
                continue
            words = line.split()
            if 2 <= len(words) <= 4:
                capital_words = sum(1 for word in words if word and word[0].isupper())
                if capital_words >= len(words) * 0.7:
                    name = line
                    print(f"👤 Extracted name: {name}")
                    break
    
    # Extract skills
    skill_keywords = ['python', 'java', 'javascript', 'react', 'node.js', 'sql', 'mongodb', 'aws', 'docker']
    found_skills = [skill.title() for skill in skill_keywords if skill in text.lower()]
    skills = ", ".join(found_skills[:10]) if found_skills else "N/A"
    print(f"🛠️ Extracted skills: {skills}")
    
    return {"Name": name, "Email": email, "Phone": phone, "Skills": skills}

# --- GOOGLE SHEETS APPEND ---
def save_to_sheet(data):
    try:
        name = data.get("Name", "N/A")
        email = data.get("Email", "N/A")
        phone = data.get("Phone", "N/A")
        skills = data.get("Skills", "N/A")
        
        print(f"Saving to sheet: {name}, {email}, {phone}, {skills}")
        
        row = [[name, email, phone, skills]]
        result = service.spreadsheets().values().append(
            spreadsheetId=SHEET_ID,
            range=RANGE,
            valueInputOption="RAW",
            body={"values": row}
        ).execute()
        
        print("Successfully saved to Google Sheets")
        return True
        
    except Exception as e:
        print(f"Error saving to sheet: {e}")
        return False

# --- WHATSAPP WEBHOOK ---
@app.route("/whatsapp", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.form.get("Body", "").strip()
    media_url = request.form.get("MediaUrl0", "")
    num_media = int(request.form.get("NumMedia", "0"))
    
    response = MessagingResponse()

    print(f"Received message: '{incoming_msg}'")
    print(f"Media URL: {media_url}")
    print(f"NumMedia: {num_media}")

    if num_media == 0 or not media_url:
        if incoming_msg:
            data = parse_resume_with_gemini(incoming_msg)
            save_to_sheet(data)
            reply = f" Text resume processed!\n\nName: {data.get('Name','N/A')}\nEmail: {data.get('Email','N/A')}\nPhone: {data.get('Phone','N/A')}\nSkills: {data.get('Skills','N/A')}"
        else:
            reply = """*Resume Parser Bot*

Send a resume as PDF file or text message.

I'll extract: Name, Email, Phone, and Skills"""
        
        response.message(reply)
        return str(response)

    # Process media file
    response.message("File received. Downloading and processing...")
    
    try:
        file_data, status = download_twilio_media(media_url)
        
        if file_data is None:
            if status == "no_credentials":
                reply = " Server configuration error. Please contact administrator."
            elif status == "auth_failed":
                reply = " Authentication failed. Please try again later."
            elif status == "not_found":
                reply = " File not found or expired. Please send the file again."
            else:
                reply = "Could not download the file. Please try again."
            
            response.message(reply)
            return str(response)
        
        file_type = detect_file_type(file_data)
        print(f"Detected file type: {file_type}")
        
        if file_type == 'application/pdf':
            text = extract_text_from_pdf(file_data)
            if text:
                print(f"Extracted text length: {len(text)} characters")
                data = parse_resume_with_gemini(text)
                save_success = save_to_sheet(data)
                
                if save_success:
                    reply = f"PDF resume processed!\n\nName: {data.get('Name','N/A')}\nEmail: {data.get('Email','N/A')}\nPhone: {data.get('Phone','N/A')}\nSkills: {data.get('Skills','N/A')}"
                else:
                    reply = "Error saving to database"
            else:
                reply = "Could not extract text from PDF."
        else:
            reply = "Unsupported file type. Please send a PDF file."
            
    except Exception as e:
        print(f" Error processing media: {e}")
        reply = f"Error processing file: {str(e)}"

    response.message(reply)
    return str(response)

@app.route("/", methods=["GET"])
def home():
    twilio_status = "Configured" if (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN) else "Missing"
    gemini_status = "Active" if GEMINI_API_KEY else "Not configured"
    
    return f"""
    WhatsApp Resume Parser is running!<br><br>
    
    Status:<br>
    - Twilio Auth: {twilio_status}<br>
    - Gemini AI: {gemini_status}<br><br>
    
    Send a PDF resume to your WhatsApp number to test.
    """

if __name__ == "__main__":
    print("WhatsApp Resume Parser Started")
    
    if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
        print("✅ Twilio authentication configured")
    else:
        print("Twilio credentials missing - media download will fail")
        print("Set environment variables: TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN")
        print("Or create 'twilio_credentials.json' file")
    
    app.run(port=5000, debug=True)