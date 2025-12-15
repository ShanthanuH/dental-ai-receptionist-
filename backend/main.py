# FILE: backend/main.py

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# SECURITY: Allow Vapi to talk to this server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# FAKE DATABASE: The "Brain's Memory"
appointment_slots = {
    "monday": ["10:00 AM", "2:00 PM"],
    "tuesday": ["11:00 AM", "4:00 PM"],
    "wednesday": ["9:00 AM", "3:00 PM"],
    "thursday": ["10:00 AM"],
    "friday": ["1:00 PM", "3:00 PM"]
}

# DATA MODEL: Validating what Vapi sends us
class AvailabilityRequest(BaseModel):
    day: str

@app.post("/check-availability")
def check_availability(request: AvailabilityRequest):
    # 1. Normalize the input (e.g., "Monday" -> "monday")
    day_requested = request.day.lower().strip()
    
    # 2. LOGGING: Print to the console so we can see it happening in real-time
    print(f"👀 VAPI REQUEST RECEIVED: Checking availability for {day_requested}")

    # 3. Check the "Database"
    if day_requested in appointment_slots:
        slots = appointment_slots[day_requested]
        return {"result": f"Yes, we have openings on {day_requested} at {', '.join(slots)}."}
    else:
        return {"result": "I'm sorry, we are fully booked on that day."}

@app.get("/")
def read_root():
    return {"message": "Dental AI Backend is Online 🟢"}