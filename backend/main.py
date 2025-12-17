# backend/main.py
from fastapi import FastAPI, Request
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import os
import json
import dateparser

app = FastAPI()

# --- CONFIGURATION ---
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'shaanhem@gmail.com'
TIMEZONE_OFFSET = "+05:30"

CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if CREDENTIALS_JSON:
    creds_dict = json.loads(CREDENTIALS_JSON)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

service = build('calendar', 'v3', credentials=creds)

# --- HELPER FUNCTION ---
def parse_smart_date(date_input):
    if not date_input:
        return None 
    # specific settings to handle "tomorrow" or "18th" correctly
    dt = dateparser.parse(
        str(date_input), 
        settings={'PREFER_DATES_FROM': 'future', 'DATE_ORDER': 'DMY'}
    )
    return dt

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "active"}

@app.post("/check-availability")
async def check_availability(request: Request):
    # 1. CAPTURE THE RAW JSON BODY
    try:
        body = await request.json()
        print(f"DEBUG: FULL RAW BODY RECEIVED: {body}")
    except Exception:
        print("DEBUG: Could not parse JSON body")
        return {"message": "Error reading request"}

    # 2. LOOK FOR THE DATA IN COMMON FIELDS
    # The AI might be calling it 'day', 'date', 'time', or 'argument'
    raw_input = body.get("day") or body.get("date") or body.get("time") or body.get("when")

    print(f"DEBUG: Extracted input string: {raw_input}")

    if not raw_input:
        # If we still can't find it, tell the AI to try again
        return {"message": "I received your request, but the date parameter was missing. Please check the tool configuration."}

    try:
        # 3. PARSE DATE
        date_obj = parse_smart_date(raw_input)
        
        if not date_obj:
            return {"message": f"I heard '{raw_input}', but I'm not sure which date that is. Could you please say the full date?"}

        formatted_date_str = date_obj.strftime("%Y-%m-%d")
        
        # 4. CHECK GOOGLE CALENDAR
        start_time = date_obj.replace(hour=9, minute=0, second=0).isoformat() + TIMEZONE_OFFSET
        end_time = date_obj.replace(hour=18, minute=0, second=0).isoformat() + TIMEZONE_OFFSET

        events_result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=start_time,
            timeMax=end_time,
            singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])

        if not events:
            readable_date = date_obj.strftime("%A, %B %d")
            return {"message": f"Good news! The doctor is completely free on {readable_date} from 9 AM to 6 PM."}
        
        busy_times = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                clean_time = start.split('T')[1][:5]
                busy_times.append(clean_time)
            
        return {
            "message": f"On {formatted_date_str}, the doctor is busy at: {', '.join(busy_times)}. Any other time is free."
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return {"message": "I'm having a technical issue checking the calendar."}

@app.post("/book_appointment")
async def book_appointment(request: Request):
    # Debugging booking as well
    body = await request.json()
    print(f"DEBUG: BOOKING BODY: {body}")
    
    # Extract fields manually since we are using raw Request
    day = body.get("day") or body.get("date")
    time = body.get("time")
    name = body.get("name")

    if not day or not time or not name:
        return {"status": "error", "message": "Missing fields. I need day, time, and name."}

    try:
        date_obj = parse_smart_date(day)
        if not date_obj:
             return {"status": "error", "message": f"Invalid date: {day}"}

        date_str_clean = date_obj.strftime("%Y-%m-%d")
        start_time_str = f"{date_str_clean}T{time}:00"
        
        try:
            appt_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
             return {"status": "error", "message": f"Invalid time format: {time}"}

        end_dt = appt_dt + timedelta(hours=1)
        
        event = {
            'summary': f'Dentist Appt: {name}',
            'location': 'Tanvi\'s KidCare Clinic',
            'description': 'Booked via AI Receptionist',
            'start': {'dateTime': appt_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
        }

        event_result = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        
        return {
            "status": "success", 
            "message": f"Appointment confirmed for {name} on {date_str_clean} at {time}.",
        }
        
    except Exception as e:
        print(f"Error booking: {e}")
        return {"status": "error", "message": str(e)}