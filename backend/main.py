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

# --- HELPER: VAPI EXTRACTOR ---
def get_vapi_data(body):
    """
    Extracts both the ARGUMENTS and the TOOL CALL ID.
    Returns: (args_dict, tool_call_id_string)
    """
    try:
        if "message" in body and "toolCalls" in body["message"]:
            tool_call = body["message"]["toolCalls"][0]
            tool_id = tool_call["id"]
            args = tool_call["function"]["arguments"]
            
            if isinstance(args, str):
                args = json.loads(args)
            return args, tool_id
            
        return body, None
    except Exception as e:
        print(f"DEBUG: Extraction Error: {e}")
        return {}, None

# --- HELPER: DATE PARSER ---
def parse_smart_date(date_input):
    if not date_input:
        return None 
    dt = dateparser.parse(
        str(date_input), 
        settings={'PREFER_DATES_FROM': 'future', 'DATE_ORDER': 'DMY'}
    )
    return dt

# --- HELPER: FORMAT RESPONSE FOR VAPI ---
def format_response(result_text, tool_call_id):
    """
    If we have a tool_call_id, return the specific Vapi structure.
    Otherwise, return a simple JSON (for testing).
    """
    print(f"DEBUG: Sending response -> {result_text}")
    
    if tool_call_id:
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": result_text
                }
            ]
        }
    else:
        # Fallback for simple POSTMAN tests
        return {"result": result_text}

# --- ENDPOINTS ---

@app.get("/")
def home():
    return {"status": "active"}

@app.post("/check-availability")
async def check_availability(request: Request):
    body = await request.json()
    
    # 1. Extract Args & ID
    args, tool_id = get_vapi_data(body)
    raw_input = args.get("day") or args.get("date")
    
    print(f"DEBUG: Processing '{raw_input}' for Tool ID: {tool_id}")

    if not raw_input:
        return format_response("I didn't catch the date. Could you please repeat it?", tool_id)

    try:
        # 2. Parse Date
        date_obj = parse_smart_date(raw_input)
        if not date_obj:
            return format_response(f"I'm not sure which date '{raw_input}' is. Please say the full date.", tool_id)

        formatted_date_str = date_obj.strftime("%Y-%m-%d")
        
        # 3. Check Google Calendar
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
            return format_response(f"Good news! The doctor is completely free on {readable_date} from 9 AM to 6 PM.", tool_id)
        
        busy_times = []
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            if 'T' in start:
                clean_time = start.split('T')[1][:5]
                busy_times.append(clean_time)
            
        return format_response(f"On {formatted_date_str}, the doctor is busy at: {', '.join(busy_times)}. Any other time is free.", tool_id)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        return format_response("I'm having a technical issue checking the calendar.", tool_id)

@app.post("/book_appointment")
async def book_appointment(request: Request):
    body = await request.json()
    
    # 1. Extract Args & ID
    args, tool_id = get_vapi_data(body)
    
    day = args.get("day") or args.get("date")
    time = args.get("time")
    name = args.get("name")
    
    print(f"DEBUG: Booking '{name}' on '{day}' at '{time}' (Tool ID: {tool_id})")

    if not day or not time:
        return format_response("I need both a day and a time to book the appointment.", tool_id)
    
    if not name:
         return format_response("I just need your name to finalize the booking.", tool_id)

    try:
        date_obj = parse_smart_date(day)
        if not date_obj:
             return format_response(f"Invalid date: {day}", tool_id)

        date_str_clean = date_obj.strftime("%Y-%m-%d")
        start_time_str = f"{date_str_clean}T{time}:00"
        
        try:
            appt_dt = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S")
        except ValueError:
             return format_response(f"Invalid time format: {time}. Please use HH:MM.", tool_id)

        end_dt = appt_dt + timedelta(hours=1)
        
        event = {
            'summary': f'Dentist Appt: {name}',
            'location': 'Tanvi\'s KidCare Clinic',
            'description': 'Booked via AI Receptionist',
            'start': {'dateTime': appt_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
            'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Kolkata'},
        }

        service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        
        return format_response(f"Appointment confirmed for {name} on {date_str_clean} at {time}.", tool_id)
        
    except Exception as e:
        print(f"Error booking: {e}")
        return format_response("I'm sorry, I couldn't access the booking system right now.", tool_id)