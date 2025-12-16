# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
import os
import json

app = FastAPI()

# --- CONFIGURATION ---
# We define the scope (permissions) we need
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Load credentials from Environment Variable (Best for Render)
# OR from a local file (Best for local testing)
CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

if CREDENTIALS_JSON:
    # If on Render, load from the environment variable string
    creds_dict = json.loads(CREDENTIALS_JSON)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    # If local, load from the file you downloaded
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

service = build('calendar', 'v3', credentials=creds)

class Appointment(BaseModel):
    day: str  # Format: "2024-05-20" (ISO format is best for machines)
    time: str # Format: "10:00"
    name: str

@app.get("/")
def home():
    return {"status": "active", "integration": "Google Calendar"}

@app.get("/check_availability")
def check_availability(day: str):
    # day format should be YYYY-MM-DD ideally, but let's handle simple string checks first
    # For a demo, we will just list events on that day to see what's busy.
    
    # Simple Logic: Convert "Tuesday" to a date? 
    # To keep it simple for the AI, let's ask the AI to send ISO dates (YYYY-MM-DD).
    # But for now, we'll return a mock response to ensure connection works, 
    # OR you can implement real "list events" logic if you want to go deep.
    
    return {"message": "Calendar connected. Please ask for a specific slot to book."}

@app.post("/book_appointment")
def book_appointment(appt: Appointment):
    try:
        # 1. Parse the date and time
        # We expect the AI to send: day="2023-12-25", time="14:00"
        start_time_str = f"{appt.day}T{appt.time}:00"
        end_time_str = f"{appt.day}T{int(appt.time.split(':')[0]) + 1}:{appt.time.split(':')[1]}:00" # 1 hour duration
        
        # 2. Create the Event Object
        event = {
            'summary': f'Dentist Appt: {appt.name}',
            'location': 'Tanvi\'s KidCare Clinic',
            'description': 'Booked via AI Receptionist',
            'start': {
                'dateTime': start_time_str,
                'timeZone': 'Asia/Kolkata', # Change to your timezone
            },
            'end': {
                'dateTime': end_time_str,
                'timeZone': 'Asia/Kolkata',
            },
        }

        # 3. Insert into Google Calendar
        event_result = service.events().insert(calendarId='shaanhem@gmail.com', body=event).execute()
        
        return {
            "status": "success", 
            "message": f"Booked for {appt.name} on {appt.day} at {appt.time}",
            "link": event_result.get('htmlLink')
        }
        
    except Exception as e:
        print(f"Error: {e}")
        return {"status": "error", "message": str(e)}