# FILE: backend/main.py
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import json

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# DATABASE
appointment_slots = {
    "monday": ["10:00 AM", "2:00 PM"],
    "tuesday": ["11:00 AM", "4:00 PM"],
    "wednesday": ["9:00 AM", "3:00 PM"],
    "thursday": ["10:00 AM"],
    "friday": ["1:00 PM", "3:00 PM"]
}

@app.post("/check-availability")
async def check_availability(request: Request):
    data = await request.json()
    print(f"📨 Data Received: {data}")
    
    day = None
    tool_call_id = None

    # 1. UNWRAP THE VAPI NESTED DATA
    try:
        if "message" in data and "toolCalls" in data["message"]:
            tool_call = data["message"]["toolCalls"][0]
            
            # CRITICAL: Grab the ID so we can reply to the specific request
            tool_call_id = tool_call["id"]
            
            arguments = tool_call["function"]["arguments"]
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            
            day = arguments.get("day")
    except Exception as e:
        print(f"⚠️ Error parsing Vapi structure: {e}")

    # Fallback for simple testing
    if not day and "day" in data:
        day = data["day"]

    # 2. CALCULATE THE ANSWER
    response_text = "I could not understand which day you wanted."
    
    if day:
        day_clean = day.lower().strip()
        print(f"🗓️ Checking schedule for: {day_clean}")
        
        if day_clean in appointment_slots:
            slots = appointment_slots[day_clean]
            response_text = f"Yes, we have openings on {day_clean} at {', '.join(slots)}."
        else:
            response_text = f"I'm sorry, we are fully booked on {day_clean}."

    # 3. FORMAT THE RESPONSE FOR VAPI
    # If we have an ID, we MUST return this specific format:
    if tool_call_id:
        return {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": response_text
                }
            ]
        }
    else:
        # Fallback for local testing (no ID)
        return {"result": response_text}

@app.get("/")
def read_root():
    return {"message": "Dental AI Backend is Online 🟢"}