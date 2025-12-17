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
CALENDAR_ID = 'shaanhem@gmail.com' # Your calendar email
TIMEZONE_OFFSET = "+05:30"

CREDENTIALS_JSON = os.environ.get("GOOGLE_CREDENTIALS_JSON")
if CREDENTIALS_JSON:
    creds_dict = json.loads(CREDENTIALS_JSON)
    creds = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
else:
    creds = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)

service = build('calendar', 'v3', credentials=creds)

# --- HELPER: VAPI ARGUMENT EXTRACTOR ---
def get_args_from_vapi(body):
    """
    Extracts arguments from the deep Vapi JSON structure.
    Returns a dictionary of arguments (e.g., {'day': 'Monday'}).
    """
    try:
        # 1. Check if it's a Vapi Tool Call
        if "message" in body and "toolCalls" in body["message"]:
            tool_call = body["message"]["toolCalls"][0]
            args = tool_call["function"]["arguments"]
            
            # Vapi sometimes sends args as a Dict, sometimes as a JSON String
            if isinstance(args, str):
                return json.loads(args)
            return args
            
        # 2. Fallback for direct testing (Postman/Curl)
        return body
    except Exception as e:
        print(f"DEBUG: Extraction Error: {e}")
        return {}

# --- HELPER: DATE PARSER ---
def parse_smart_date(date_input):
    if not date_input:
        return None 
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
    # 1. Get the Raw JSON
    body = await request.json()
    print(f"DEBUG: Body received") # Keeping logs cleaner now
    
    # 2. Extract Arguments using new helper
    args = get_args_from_vapi(body)
    raw_input = args.get("day") or args.get("date")
    
    print(f"DEBUG: FINAL EXTRACTED DAY: '{raw_input}'")

    if not raw_input:
        return {"result": "I didn't catch the date. Could you please repeat it?"}

    try:
        # 3. Parse Date
        date_obj = parse_smart_date(raw_input)
        if not date_obj:
            return {"result": f"I'm not sure which date '{raw_input}' is. Please say the full date."}

        formatted_date_str = date_obj.strftime("%Y-%m-%d")
        
        # 4. Check Google Calendar
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
            # Vapi expects a "result" field often, but "message" works too.
            return {"result": f"Good news! The doctor is completely free on {readable_date} from 9 AM to 6 PM."}
        
        busy_times = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                clean_time = start.split('T')[1][:5]
                busy_times.append(clean_time)
            
        return {
            "result": f"On {formatted_date_str}, the doctor is busy at: {', '.join(busy_times)}. Any other time is free."
        }

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return {"result": "I'm having a technical issue checking the calendar."}

@app.post("/book_appointment")
async def book_appointment(request: Request):
    body = await request.json()
    
    # 1. Extract Args
    args = get_args_from_vapi(body)
    
    day = args.get("day") or args.get("date")
    time = args.get("time")
    name = args.get("name") # AI needs to ask for name if not provided
    
    print(f"DEBUG: Booking Request -> Day:{day}, Time:{time}, Name:{name}")

    if not day or not time:
        return {"result": "I need both a day and a time to book the appointment."}
    
    if not name:
         return {"result": "I just need your name to finalize the booking."}

    try:
        date_obj = parse_smart_date(day)
        if not date_obj:
             return {"result": f"Invalid date: {day}"}

        date_str_clean = date_obj.strftime("%Y-%m-%d")
        start_time_str = f"{date_str_clean}T{time}:00"
        
        try:
            appt_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
             return {"result": f"Invalid time format: {time}. Please use HH:MM."}

        end_dt = appt_dt + timedelta(hours=1)
        
        event = {
            'summary': f'Dentist Appt: {name}',
            'location': 'Tanvi\'s KidCare Clinic',
            'description': 'Booked via AI Receptionist',
            'start': {'dateTime': appt_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
        }

        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        
        return {
            "result": f"Appointment confirmed for {name} on {date_str_clean} at {time}."
        }
        
    except Exception as e:
        print(f"Error booking: {e}")
        return {"result": "I'm sorry, I couldn't access the booking system right now."}