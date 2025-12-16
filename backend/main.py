# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.oauth2 import service_account
from googleapiclient.discovery import build
import datetime
from datetime import datetime, timedelta
import os
import json

app = FastAPI()

# --- CONFIGURATION ---
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

# --- DATA MODELS ---

# 1. Model for checking availability (The AI sends just the day)
class DateRequest(BaseModel):
    day: str  # Format: "2025-12-17"

# 2. Model for booking (The AI sends day, time, and name)
class Appointment(BaseModel):
    day: str  # Format: "2024-05-20"
    time: str # Format: "10:00"
    name: str

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "active", "integration": "Google Calendar"}

# UPDATED: Changed to POST and dashed-url to match the AI's request
@app.post("/check-availability")
def check_availability(request: DateRequest):
    day = request.day
    print(f"Checking availability for: {day}") # Log for debugging

    try:
        # 1. Parse the requested date (Expected format: YYYY-MM-DD)
        date_obj = datetime.strptime(day, "%Y-%m-%d")
        
        # 2. Define the "Work Day" (9 AM to 6 PM IST)
        # RFC3339 format with +05:30 offset
        start_time = date_obj.replace(hour=9, minute=0).isoformat() + "+05:30"
        end_time = date_obj.replace(hour=18, minute=0).isoformat() + "+05:30"

        # 3. Ask Google: "Give me all events between 9 AM and 6 PM"
        CALENDAR_ID = 'shaanhem@gmail.com' 
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        # 4. Formulate the Answer
        if not events:
            return {"message": f"Good news! The doctor is completely free on {day} from 9 AM to 6 PM."}
        
        busy_times = []
        for event in events:
            # Get the start time
            start = event['start'].get('dateTime', event['start'].get('date'))
            # Clean it up to just show HH:MM (e.g., "14:00")
            if 'T' in start:
                clean_time = start.split('T')[1][:5]
                busy_times.append(clean_time)
            
        return {
            "message": f"On {day}, the doctor is busy at these times: {', '.join(busy_times)}. Any other time is free."
        }

    except Exception as e:
        print(f"Error checking availability: {e}")
        return {"message": "I'm having trouble checking the schedule specifically, but you can try proposing a time."}

@app.post("/book_appointment")
def book_appointment(appt: Appointment):
    try:
        # 1. Parse the date and time
        # We expect the AI to send: day="2023-12-25", time="14:00"
        start_time_str = f"{appt.day}T{appt.time}:00"
        # Calculate end time (1 hour later)
        appt_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        end_dt = appt_dt + timedelta(hours=1)
        end_time_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
        
        # 2. Create the Event Object
        event = {
            'summary': f'Dentist Appt: {appt.name}',
            'location': 'Tanvi\'s KidCare Clinic',
            'description': 'Booked via AI Receptionist',
            'start': {
                'dateTime': start_time_str,
                'timeZone': 'Asia/Kolkata',
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
        print(f"Error booking: {e}")
        return {"status": "error", "message": str(e)}