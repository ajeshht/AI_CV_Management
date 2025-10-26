# AI Based WhatsApp CV Parser 🤖

A smart WhatsApp bot that automatically extracts information from resumes and saves it to Google Sheets using AI.

## Features ✨

- **WhatsApp Integration**: Receive resumes via WhatsApp messages
- **AI-Powered Parsing**: Uses Google Gemini AI to extract information from resumes
- **PDF Processing**: Automatically extracts text from PDF files
- **Google Sheets Integration**: Saves extracted data directly to Google Sheets
- **Multi-format Support**: Handles PDF files and text messages
- **Smart Extraction**: Extracts Name, Email, Phone, and Skills from resumes

## Extracted Information 📋

- **Name**: Full name from resume
- **Email**: Email address
- **Phone**: Phone number (with country code)
- **Skills**: Technical and professional skills

## Tech Stack 🛠️

- **Backend**: Flask (Python)
- **Messaging**: Twilio WhatsApp API
- **AI**: Google Gemini AI
- **Storage**: Google Sheets API
- **PDF Processing**: pdfplumber

## Quick Start 🚀

### Prerequisites

- Python 3.8+
- Twilio Account
- Google Cloud Project
- Gemini API Access

### Installation

1. **Clone the repository**
   ```
   git clone https://github.com/ajeshht/AI_CV_Management.git
   cd AI_CV_Management
2. **Create virtual environment**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
3. **Install dependencies**
   ```
   pip install -r requirements.txt
4. **Set up environment variables**
   ```
   # Copy the example environment file
      cp .env.example .env
Edit .env file with your credentials
   ```
   # Google Sheets
   SHEET_ID=your_google_sheet_id_here
   SERVICE_ACCOUNT_FILE=credentials.json

   # Gemini AI
   GEMINI_API_KEY=your_gemini_api_key_here

   # Twilio
   TWILIO_ACCOUNT_SID=your_twilio_account_sid
   TWILIO_AUTH_TOKEN=your_twilio_auth_token

```
5.**Set up credentials**
   Download Google Service Account JSON and save as credentials.json

   Get Gemini API key from Google AI Studio

   Get Twilio credentials from Twilio Console
6. Run the application
   ```
   python app.py
```
Project Structure 📁
   whatsapp-resume-parser/
   ├── app.py                 # Main Flask application
   ├── requirements.txt       # Python dependencies
   ├── .env.example          # Environment variables template
   ├── .gitignore           # Git ignore rules
   └── README.md            # This file
