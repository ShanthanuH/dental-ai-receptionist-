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

# THE REAL DATABASE
appointment_slots = {
    "monday": ["10:00 AM", "2:00 PM"],
    "tuesday": ["11:00 AM", "4:00 PM"],
    "wednesday": ["9:00 AM", "3:00 PM"],
    "thursday": ["10:00 AM"],
    "friday": ["1:00 PM", "3:00 PM"]
}

@app.post("/check-availability")
async def check_availability(request: Request):
    # 1. Get the raw data
    data = await request.json()
    print(f"📨 Data Received: {data}")
    
    day = None

    # 2. UNWRAP THE RUSSIAN DOLL (Vapi Structure)
    try:
        if "message" in data and "toolCalls" in data["message"]:
            # Dig into the nested structure
            tool_call = data["message"]["toolCalls"][0]
            arguments = tool_call["function"]["arguments"]
            
            # Vapi sometimes sends arguments as a String, sometimes as a Dict
            # We handle both cases here:
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            
            day = arguments.get("day")
    except Exception as e:
        print(f"⚠️ Error parsing Vapi structure: {e}")

    # 3. BACKUP PLAN (If sending simple JSON)
    if not day and "day" in data:
        day = data["day"]

    # 4. THE BUSINESS LOGIC
    if day:
        day_clean = day.lower().strip()
        print(f"🗓️ Checking schedule for: {day_clean}")
        
        if day_clean in appointment_slots:
            slots = appointment_slots[day_clean]
            return {"result": f"Yes, we have openings on {day_clean} at {', '.join(slots)}."}
        else:
            return {"result": f"I'm sorry, we are fully booked on {day_clean}."}
    
    # 5. FAILURE RESPONSE
    print("❌ Could not find 'day' in payload")
    return {"result": "I could not understand which day you wanted. Please try again."}

@app.get("/")
def read_root():
    return {"message": "Dental AI Backend is Online 🟢"}