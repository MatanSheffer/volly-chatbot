# Volly Chatbot

A LangChain/LangGraph-based assistant for organizing beach volleyball games over WhatsApp, built as a learning project that taught how to build an AI agent for coordinating events with your husband.

## Purpose
- Automates invite generation, RSVP logging, and player Q&A for upcoming beach volleyball games.
- Demonstrates how to design an agent with tools that reason over structured data, conversational history, and personalized context for each player.
- Uses WhatsApp + Meta Graph webhook flow so replies feel like a natural chat while still being backed by databases and LLM reasoning.

## Key Technologies
- **Agent stack**: `langchain_google_genai.ChatGoogleGenerativeAI` with `langgraph.prebuilt.create_react_agent` plus custom `get_game_details`, `check_availability`, and `log_response` tools.
- **Webhook API**: `FastAPI` listening for WhatsApp messages, normalizing phone numbers, compiling context, and calling the agent executor (`agent_logic.py`).
- **WhatsApp integration**: `httpx` POST calls to Meta Graph API guarded by tokens loaded via `.env`.
- **Persistence**: PostgreSQL via `psycopg2`, schema initialization in `init_db.py`, and helpers in `database.py` to track players, games, responses, and conversation history.
- **Prompt design**: Templates in `prompts.py` for system behavior, invites, onboarding, and graceful errors.
- **Utilities**: Phone normalization/formatting helpers in `phone_utils.py`, Pydantic models in `models.py`.

## How It Works
1. Incoming WhatsApp webhook hits `/webhook`, where FastAPI validates the message, fetches player info, recent convo history, and game status.
2. Context is compiled into a LangChain message sequence and sent to the LangGraph agent, which chooses when to call structured-data tools.
3. Tool responses help the agent give accurate details, while the reply is stored in `conversation_history` and forwarded to WhatsApp via the Meta Graph API.
4. Running `main.py --new-game "<date>"` triggers `setup_new_game`, which invites all active players by asking the agent to craft personalized texts.

## Setup
1. Copy `.env.example` (if available) to `.env` and populate `WHATSAPP_TOKEN`, `PHONE_NUMBER_ID`, `VERIFY_TOKEN`, plus database credentials (`user`, `password`, `host`, `port`, `dbname`).
2. Install dependencies: `pip install -r requirements.txt`.
3. Initialize DB: `python init_db.py`.
4. Start the app: `python main.py`.

## Skills Demonstrated
- Designing tool-augmented agents for practical tasks.
- Mixing FastAPI webhook handling with asynchronous WhatsApp responses.
- Using database-backed history/context to guide the AI, ensuring continuity in conversations.
- Normalizing and formatting phone numbers for multiple integration points (WhatsApp, DB lookups).

This README captures the learning journey of building an AI assistant that keeps your beach volleyball plans organized and conversational.

