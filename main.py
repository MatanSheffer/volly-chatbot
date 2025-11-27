from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel

app = FastAPI()

class WhatsAppMessage(BaseModel):
    # Define the expected structure of the WhatsApp webhook payload here
    # For now, we'll keep it flexible as it depends on the provider (e.g., Twilio, Meta)
    # This is a placeholder structure
    object: str | None = None
    entry: list | None = None

@app.get("/")
async def read_root():
    return {"status": "ok", "message": "WhatsApp Agent is running"}

@app.post("/whatsapp")
async def receive_whatsapp(request: Request):
    """
    Webhook endpoint to receive messages from WhatsApp.
    """
    try:
        # Parse the incoming JSON payload
        payload = await request.json()
        print(f"Received payload: {payload}")
        
        # TODO: Process the message here
        # 1. Extract message content and sender
        # 2. Interact with database (Players, Games, Responses)
        # 3. Use AI to analyze intent (future step)
        
        return {"status": "received"}
    except Exception as e:
        print(f"Error processing webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal Server Error")
