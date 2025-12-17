# backend/main.py
from fastapi import FastAPI, Request
from pydantic import BaseModel
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os
import json
import dateparser # NEW: Handles "18th Dec", "Tomorrow", etc.

app = FastAPI()

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'shaanhem@gmail.com' # Your calendar ID
TIMEZONE_OFFSET = "+05:30" # IST Offset

# Load credentials
CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

if CREDENTIALS_JSON:
    creds_dict = json.loads(CREDENTIALS_JSON)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

service = build('calendar', 'v3', credentials=creds)

# --- DATA MODELS ---

# We use "day" but accept "date" too, just in case the AI gets confused.
# defaulting to None prevents the 422 Crash.
class DateRequest(BaseModel):
    day: str = None
    date: str = None 

class Appointment(BaseModel):
    day: str = None
    time: str
    name: str

# --- HELPER FUNCTION ---
def parse_smart_date(date_input):
    """
    Converts natural language (e.g., '18th of December') into a python datetime object.
    Returns None if it fails.
    """
    if not date_input:
        return None
        
    print(f"DEBUG: Parsing date string -> '{date_input}'")
    
    # settings={'PREFER_DATES_FROM': 'future'} ensures that if you say "Dec 18" 
    # and today is Dec 20, it assumes you mean NEXT year.
    dt = dateparser.parse(
        date_input, 
        settings={'PREFER_DATES_FROM': 'future', 'DATE_ORDER': 'DMY'}
    )
    return dt

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "active", "integration": "Google Calendar"}

@app.post("/check-availability")
def check_availability(request: DateRequest):
    # 1. robustly get the input string
    raw_input = request.day or request.date
    print(f"DEBUG: Received check-availability request: {raw_input}")

    if not raw_input:
        return {"message": "I didn't catch the day. Could you repeat which date you want to check?"}

    try:
        # 2. Parse the date
        date_obj = parse_smart_date(raw_input)
        
        if not date_obj:
            return {"message": f"I'm sorry, I didn't quite understand the date '{raw_input}'. Please try saying the full date, like 'December 18th'."}

        # 3. Format strings for Google Calendar
        formatted_date_str = date_obj.strftime("%Y-%m-%d")
        print(f"DEBUG: Querying Google Calendar for: {formatted_date_str}")
        
        # Define 9 AM to 6 PM IST
        start_time = date_obj.replace(hour=9, minute=0, second=0).isoformat() + TIMEZONE_OFFSET
        end_time = date_obj.replace(hour=18, minute=0, second=0).isoformat() + TIMEZONE_OFFSET

        # 4. Call Google API
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        # 5. Build Response
        if not events:
            readable_date = date_obj.strftime("%A, %B %d")
            return {"message": f"Good news! The doctor is completely free on {readable_date} from 9 AM to 6 PM."}
        
        busy_times = []
        for event in events:
            # Handle full day vs timed events
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                clean_time = start.split('T')[1][:5] # Extract HH:MM
                busy_times.append(clean_time)
            
        return {
            "message": f"On {formatted_date_str}, the doctor is busy at: {', '.join(busy_times)}. Any other time is free."
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        # Return a polite error to the voice bot so it doesn't just go silent
        return {"message": "I'm having a technical issue checking the calendar right now. Please try again in a moment."}

@app.post("/book_appointment")
def book_appointment(appt: Appointment):
    print(f"DEBUG: Booking request for {appt.name} on {appt.day} at {appt.time}")
    
    try:
        # 1. Parse date
        date_obj = parse_smart_date(appt.day)
        if not date_obj:
             return {"status": "error", "message": f"Invalid date: {appt.day}"}

        date_str_clean = date_obj.strftime("%Y-%m-%d")

        # 2. Construct ISO Timestamps
        start_time_str = f"{date_str_clean}T{appt.time}:00"
        
        # Verify valid time format
        try:
            appt_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
             return {"status": "error", "message": f"Invalid time format: {appt.time}"}

        end_dt = appt_dt + timedelta(hours=1)
        
        # 3. Create Event Body
        event = {
            'summary': f'Dentist Appt: {appt.name}',
            'location': 'Tanvi\'s KidCare Clinic',
            'description': 'Booked via AI Receptionist',
            'start': {
                'dateTime': appt_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
            'end': {
                'dateTime': end_dt.isoformat(),
                'timeZone': 'Asia/Kolkata',
            },
        }

        # 4. Insert to Google
        event_result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        
        return {
            "status": "success", 
            "message": f"Appointment confirmed for {appt.name} on {date_str_clean} at {appt.time}.",
            "link": event_result.get('htmlLink')
        }
        
    except Exception as e:
        print(f"Error booking: {e}")
        return {"status": "error", "message": str(e)}