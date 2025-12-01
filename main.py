import os
import json
import httpx
import uvicorn
import argparse
import asyncio
from fastapi import FastAPI, Request, HTTPException, Query
from dotenv import load_dotenv
from agent_logic import agent_executor
from database import (
    create_game, 
    get_active_players, 
    get_conversation_history, 
    add_message_to_history,
    get_player_by_phone,
    get_player_game_status
)
from phone_utils import normalize_phone_number, format_for_whatsapp
from prompts import INVITE_GENERATION_PROMPT_TEMPLATE, NEW_PLAYER_GREETING_TEMPLATE

# Load environment variables
load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
PHONE_NUMBER_ID = os.getenv("PHONE_NUMBER_ID")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")

app = FastAPI()

async def send_whatsapp_message(to_number: str, text_body: str):
    """
    Sends a WhatsApp message using the Meta Graph API.
    """
    url = f"https://graph.facebook.com/v21.0/{PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "messaging_product": "whatsapp",
        "to": to_number,
        "type": "text",
        "text": {"body": text_body},
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, headers=headers, json=data)
            response.raise_for_status()
            print(f"Message sent to {to_number}: {response.json()}")
        except httpx.HTTPStatusError as e:
            print(f"Failed to send message: {e.response.text}")
        except Exception as e:
            print(f"Error sending message: {e}")

def extract_text_content(content) -> str:
    """
    Extracts text content from LangChain agent response which might be structured.
    """
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                return block.get("text")
        # Fallback if no text block found
        return str(content)
    elif isinstance(content, dict):
        if content.get("type") == "text":
            return content.get("text")
        return str(content)
    return str(content)

async def setup_new_game(game_date: str):
    """
    Creates a new game and invites all active players.
    """
    print(f"Setting up a new game for {game_date}...")
    
    # 1. Create the game in the DB
    game = create_game(game_date)
    if not game:
        print("Failed to create game. Aborting setup.")
        return

    print(f"Game created with ID: {game['id']}")

    # 2. Get active players
    players = get_active_players()
    if not players:
        print("No active players found.")
        return

    print(f"Found {len(players)} active players. Sending invites...")

    # 3. Send invites

    for player in players:
        phone = player['phone_number']
        name = player['name']
        country = player.get('country', 'Israel') # Default to Israel if not set
        language = player.get('language', 'Hebrew') # Default to Hebrew if not set
        
        formatted_phone = format_for_whatsapp(phone)
        
        # Fetch history to provide context
        history = get_conversation_history(phone, limit=5)
        formatted_history = [(msg['role'], msg['content']) for msg in history]
        
        # Construct the prompt for the agent using template
        prompt = INVITE_GENERATION_PROMPT_TEMPLATE.format(
            player_name=name,
            game_date=game_date,
            language=language
        )
        
        # Add the prompt to the history for the agent's context
        messages = formatted_history + [("user", prompt)]
        
        try:
            # Invoke the agent to generate the invite
            response = await agent_executor.ainvoke({"messages": messages})
            invite_message = extract_text_content(response["messages"][-1].content)
            
            # Send the message
            await send_whatsapp_message(formatted_phone, invite_message)
            
            # Save the invite to history so the conversation continues naturally
            add_message_to_history(phone, "ai", invite_message)
            
        except Exception as e:
            print(f"Error generating/sending invite for {name}: {e}")
            # Fallback to hardcoded message if agent fails
            if language.lower() == 'hebrew':
                fallback_msg = f"היי! מארגנים משחק כדורעף ב-{game_date}. את/ה בא/ה? תענה/י 'כן' או 'לא'."
            else:
                fallback_msg = f"Hey! We're setting up a volleyball game on {game_date}. Are you in? Reply with 'Yes' or 'No'."
            await send_whatsapp_message(formatted_phone, fallback_msg)
            add_message_to_history(phone, "ai", fallback_msg)
        
    print("All invites sent!")

@app.get("/webhook")
async def verify_webhook(
    mode: str = Query(..., alias="hub.mode"),
    token: str = Query(..., alias="hub.verify_token"),
    challenge: str = Query(..., alias="hub.challenge"),
):
    """
    Verifies the webhook with Meta.
    """
    try:
        if mode == "subscribe" and token == VERIFY_TOKEN:
            print("Webhook verified successfully!")
            return int(challenge)
        else:
            raise HTTPException(status_code=403, detail="Verification failed")
    except Exception as e:
        print(f"Error processing webhook: {e}")
        # Return 200 to prevent WhatsApp from retrying indefinitely in case of logic errors
        return {"status": "error", "message": str(e)}

@app.post("/webhook")
async def webhook_handler(request: Request):
    """
    Handles incoming WhatsApp messages.
    """
    try:
        print("Webhook triggered!")
        payload = await request.json()
        # print(f"Received payload: {json.dumps(payload, indent=2)}")

        # Check if this is a message (not a status update)
        entry = payload.get("entry", [])
        if not entry:
            print("No entry in payload")
            return {"status": "ignored", "reason": "no entry"}

        changes = entry[0].get("changes", [])
        if not changes:
            print("No changes in payload")
            return {"status": "ignored", "reason": "no changes"}

        value = changes[0].get("value", {})
        
        # Ignore status updates (e.g., sent, delivered, read)
        if "statuses" in value:
            # print("Ignoring status update")
            return {"status": "ignored", "reason": "status update"}

        messages = value.get("messages", [])
        if not messages:
            print("No messages in value")
            return {"status": "ignored", "reason": "no messages"}

        # Process the first message
        message = messages[0]
        sender_id = message.get("from")
        
        # We only handle text messages for now
        if message.get("type") != "text":
            print(f"Ignoring non-text message type: {message.get('type')}")
            return {"status": "ignored", "reason": "not a text message"}
            
        message_body = message["text"]["body"]
        print(f"Processing message from {sender_id}: {message_body}")
        
        # Normalize the phone number for consistent database lookups
        normalized_sender = normalize_phone_number(sender_id)

        # 1. Lookup player info
        print("Looking up player...")
        player = get_player_by_phone(normalized_sender)
        
        if not player:
            # New player onboarding
            print(f"Unknown player: {sender_id}")
            await send_whatsapp_message(sender_id, NEW_PLAYER_GREETING_TEMPLATE)
            add_message_to_history(normalized_sender, "user", message_body)
            add_message_to_history(normalized_sender, "ai", NEW_PLAYER_GREETING_TEMPLATE)
            return {"status": "new_player_onboarding"}
        
        player_name = player['name']
        player_id = player['id']
        print(f"Player identified: {player_name}")
        
        # 2. Get player's current game status
        game_status = get_player_game_status(normalized_sender)
        status_info = ""
        if game_status and "error" not in game_status:
            status_info = f"Current status for next game: {game_status['status']}"
        else:
            status_info = "No upcoming game or no response yet."

        # 3. Fetch conversation history
        print("Fetching history...")
        history = get_conversation_history(normalized_sender, limit=10)
        formatted_history = []
        for msg in history:
            formatted_history.append((msg['role'], msg['content']))
            
        # 4. Add player context as a system message, then user message
        # This gives the agent full context about who they're talking to
        player_context = (
            f"[CONTEXT] You are talking to {player_name} (phone: {normalized_sender}). "
            f"{status_info}"
        )
        formatted_history.append(("system", player_context))
        formatted_history.append(("user", message_body))

        # 5. Invoke the agent with full context
        print("Invoking agent...")
        # Pass the phone number in config so tools can access it
        config = {"configurable": {"player_phone": normalized_sender}}
        response = agent_executor.invoke({"messages": formatted_history}, config=config)
        
        # Get the last message from the agent (the AI response)
        ai_message = extract_text_content(response["messages"][-1].content)
        print(f"AI Response: {ai_message}")

        # 6. Save messages to DB
        print("Saving to DB...")
        add_message_to_history(normalized_sender, "user", message_body)
        add_message_to_history(normalized_sender, "ai", ai_message)

        # 7. Send the response back to WhatsApp
        print("Sending response to WhatsApp...")
        await send_whatsapp_message(sender_id, ai_message)

        return {"status": "processed"}

    except Exception as e:
        print(f"Error processing webhook: {e}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Volly Chatbot Server")
    parser.add_argument("--new-game", type=str, help="Date and time for a new game (e.g., '2025-12-05 18:00')")
    args = parser.parse_args()

    if args.new_game:
        asyncio.run(setup_new_game(args.new_game))
    
    # Always run the server to listen for replies
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
