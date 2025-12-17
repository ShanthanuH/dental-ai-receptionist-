# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta # Cleaned up imports
import os
import json

app = FastAPI()

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/calendar']

# Load credentials
CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")

if CREDENTIALS_JSON:
    creds_dict = json.loads(CREDENTIALS_JSON)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

service = build('calendar', 'v3', credentials=creds)

# --- DATA MODELS ---
class DateRequest(BaseModel):
    day: str  # Can now handle "Monday", "Tomorrow", "2025-12-17"

class Appointment(BaseModel):
    day: str
    time: str
    name: str

# --- HELPER FUNCTION: THE FIX ---
def get_date_object(date_str):
    """
    Converts 'Monday', 'tomorrow', or '2025-12-17' into a datetime object.
    """
    date_str = date_str.strip().lower()
    today = datetime.now()
    
    # 1. Try Standard ISO Format (YYYY-MM-DD)
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        pass # Not ISO, try natural language

    # 2. Handle "today" and "tomorrow"
    if date_str == "today":
        return today
    if date_str == "tomorrow":
        return today + timedelta(days=1)

    # 3. Handle Weekdays (e.g., "monday", "friday")
    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if date_str in weekdays:
        target_idx = weekdays.index(date_str)
        current_idx = today.weekday() # Monday is 0, Sunday is 6
        
        # Calculate difference
        days_ahead = target_idx - current_idx
        
        # If the day has passed or is today, assume they mean NEXT week's occurrence
        # (Change to just < 0 if you want "Monday" on a Monday to mean TODAY)
        if days_ahead <= 0: 
            days_ahead += 7
            
        return today + timedelta(days=days_ahead)

    # If all else fails
    raise ValueError(f"Could not understand date: {date_str}")

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "active", "integration": "Google Calendar"}

@app.post("/check-availability")
def check_availability(request: DateRequest):
    raw_input = request.day
    print(f"Checking availability for: {raw_input}")

    try:
        # --- FIX: Use the helper function instead of direct strptime ---
        date_obj = get_date_object(raw_input)
        
        # Convert back to string for the response message later
        formatted_date = date_obj.strftime("%Y-%m-%d") 
        
        # Define the "Work Day" (9 AM to 6 PM IST)
        start_time = date_obj.replace(hour=9, minute=0, second=0).isoformat()
        end_time = date_obj.replace(hour=18, minute=0, second=0).isoformat()
        
        # Add Timezone manually if needed, or rely on 'Z' if your server is UTC
        # For India (IST), we append offset. 
        start_time += "+05:30"
        end_time += "+05:30"

        CALENDAR_ID = 'shaanhem@gmail.com' 
        
        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        if not events:
            return {"message": f"Good news! The doctor is completely free on {formatted_date} (that's {raw_input}) from 9 AM to 6 PM."}
        
        busy_times = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                clean_time = start.split('T')[1][:5]
                busy_times.append(clean_time)
            
        return {
            "message": f"On {formatted_date}, the doctor is busy at: {', '.join(busy_times)}. Any other time is free."
        }

    except Exception as e:
        print(f"Error checking availability: {e}")
        return {"message": f"I couldn't quite understand '{raw_input}'. Could you try giving me the date, like 'January 25th' or 'tomorrow'?"}

@app.post("/book_appointment")
def book_appointment(appt: Appointment):
    try:
        # Use the same helper here just in case they send "Monday" to book
        date_obj = get_date_object(appt.day)
        date_str_clean = date_obj.strftime("%Y-%m-%d")

        start_time_str = f"{date_str_clean}T{appt.time}:00"
        
        appt_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        end_dt = appt_dt + timedelta(hours=1)
        
        # Format for Google Calendar
        # Note: Ideally, handle timezone carefully here. Assuming input is local.
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

        event_result = service.events().insert(calendarId='shaanhem@gmail.com', body=event).execute()
        
        return {
            "status": "success", 
            "message": f"Booked for {appt.name} on {date_str_clean} at {appt.time}",
            "link": event_result.get('htmlLink')
        }
        
    except Exception as e:
        print(f"Error booking: {e}")
        return {"status": "error", "message": str(e)}