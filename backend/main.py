# FILE: backend/main.py
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# SECURITY: Allow Vapi to talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FAKE DATABASE
appointment_slots = {
    "monday": ["10:00 AM", "2:00 PM"],
    "tuesday": ["11:00 AM", "4:00 PM"],
    "wednesday": ["9:00 AM", "3:00 PM"],
    "thursday": ["10:00 AM"],
    "friday": ["1:00 PM", "3:00 PM"]
}

@app.post("/check-availability")
async def check_availability(request: Request):
    # 1. GRAB THE RAW DATA (No validation, just grab it)
    body = await request.json()
    
    # 2. SPY ON IT: Print exactly what Vapi sent
    print(f"🕵️ DEBUG: Raw Vapi Payload: {body}")

    # 3. Try to find the 'day' in the mess
    # Vapi sometimes sends it directly: {"day": "Monday"}
    # Or sometimes nested: {"message": {"toolCalls": [...]}}
    
    day_requested = None
    
    # simple check: is 'day' right at the top?
    if "day" in body:
        day_requested = body["day"]
    
    # If we found a day, proceed
    if day_requested:
        day_clean = day_requested.lower().strip()
        print(f"✅ FOUND DAY: {day_clean}")
        
        if day_clean in appointment_slots:
            slots = appointment_slots[day_clean]
            return {"result": f"Yes, we have openings on {day_clean} at {', '.join(slots)}."}
        else:
            return {"result": "I'm sorry, we are fully booked on that day."}
    
    # If we couldn't find the day, tell Vapi "Error" but keep the server running
    print("❌ ERROR: Could not find 'day' in the payload.")
    return {"result": "I could not understand which day you wanted. Please try again."}

@app.get("/")
def read_root():
    return {"message": "Dental AI Backend is Online 🟢"}