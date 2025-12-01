import os
from typing import TypedDict, List
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from langchain_core.messages import BaseMessage
from langgraph.prebuilt import create_react_agent
from langgraph.graph import MessagesState
from langgraph.types import Command
from database import get_db_connection, get_player_game_status
from psycopg2.extras import RealDictCursor
from prompts import AGENT_SYSTEM_PROMPT, ERROR_MESSAGES

# Load environment variables (requires GOOGLE_API_KEY)
load_dotenv()

# 1. Setup Model
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

# 2. Define Tools with improved design
@tool
def get_game_details(date_query: str = "next") -> str:
    """
    Gets details about a volleyball game (time, location, number of confirmed players).
    Use this when a player asks about when/where the game is.
    
    Args:
        date_query: The date to check for (YYYY-MM-DD), or 'next' for the upcoming game.
    
    Returns:
        Game details including time, location, and player count.
    """
    conn = get_db_connection()
    if not conn:
        return ERROR_MESSAGES["database_error"]
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find the game
        if date_query.lower() == "next":
            cursor.execute("""
                SELECT * FROM games 
                WHERE start_time > NOW() 
                ORDER BY start_time ASC 
                LIMIT 1
            """)
        else:
            cursor.execute("""
                SELECT * FROM games 
                WHERE start_time::date = %s::date
            """, (date_query,))
            
        game = cursor.fetchone()
        
        if not game:
            return ERROR_MESSAGES["no_upcoming_game"]
            
        game_id = game['id']
        
        # Get number of confirmed players
        cursor.execute("""
            SELECT COUNT(*) as confirmed_count
            FROM game_responses
            WHERE game_id = %s AND status = 'confirmed'
        """, (game_id,))
        
        count_result = cursor.fetchone()
        confirmed_count = count_result['confirmed_count'] if count_result else 0
        
        # Format the response naturally
        game_time = game['start_time']
        location = game['location']
        max_players = game['max_players']
        
        return (
            f"Game is at {location} on {game_time}. "
            f"Currently {confirmed_count}/{max_players} confirmed."
        )
        
    except Exception as e:
        print(f"Error getting game details: {e}")
        return ERROR_MESSAGES["database_error"]
    finally:
        if conn:
            conn.close()

@tool
def check_availability(date_query: str = "next") -> str:
    """
    Checks who's coming to the game (shows list of confirmed, declined, and pending players).
    Use this when a player asks "who's coming?" or "who else is in?".
    
    Args:
        date_query: The date to check for (YYYY-MM-DD), or 'next' for the upcoming game.
    
    Returns:
        List of players by response status.
    """
    conn = get_db_connection()
    if not conn:
        return ERROR_MESSAGES["database_error"]
    
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Find the game
        if date_query.lower() == "next":
            cursor.execute("""
                SELECT * FROM games 
                WHERE start_time > NOW() 
                ORDER BY start_time ASC 
                LIMIT 1
            """)
        else:
            cursor.execute("""
                SELECT * FROM games 
                WHERE start_time::date = %s::date
            """, (date_query,))
            
        game = cursor.fetchone()
        
        if not game:
            return ERROR_MESSAGES["no_upcoming_game"]
            
        game_id = game['id']
        
        # Get responses
        cursor.execute("""
            SELECT p.name, gr.status 
            FROM game_responses gr
            JOIN players p ON gr.player_id = p.id
            WHERE gr.game_id = %s
        """, (game_id,))
        
        responses = cursor.fetchall()
        
        confirmed = [r['name'] for r in responses if r['status'] == 'confirmed']
        maybe = [r['name'] for r in responses if r['status'] == 'maybe']
        declined = [r['name'] for r in responses if r['status'] == 'declined']
        
        result_parts = []
        if confirmed:
            result_parts.append(f"Confirmed ({len(confirmed)}/{game['max_players']}): {', '.join(confirmed)}")
        if maybe:
            result_parts.append(f"Maybe: {', '.join(maybe)}")
        if declined:
            result_parts.append(f"Can't make it: {', '.join(declined)}")
        
        if not result_parts:
            return "No responses yet for this game."
            
        return "\\n".join(result_parts)
        
    except Exception as e:
        print(f"Error checking availability: {e}")
        return ERROR_MESSAGES["database_error"]
    finally:
        if conn:
            conn.close()

@tool
def log_response(phone_number: str, status: str) -> str:
    """
    Records a player's response for the next upcoming game.
    Use this when a player confirms, declines, or is unsure about attending.
    
    Args:
        phone_number: The player's phone number (you'll receive this in the context)
        status: Player's response - must be one of: 'confirmed', 'declined', 'maybe', 'pending'
    
    Returns:
        Confirmation message of the logged response.
    """
    # Validate status
    valid_statuses = ['confirmed', 'declined', 'maybe', 'pending']
    if status.lower() not in valid_statuses:
        return f"Invalid status. Must be one of: {', '.join(valid_statuses)}"
    
    conn = get_db_connection()
    if not conn:
        return ERROR_MESSAGES["database_error"]
        
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # 1. Find Player by phone using the helper function that handles normalization
        from database import get_player_by_phone as db_get_player_by_phone
        player = db_get_player_by_phone(phone_number)
        
        if not player:
            return ERROR_MESSAGES["player_not_found"]
            
        player_id = player['id']
        player_name = player['name']
        
        # 2. Find Next Game
        cursor.execute("""
            SELECT id, start_time FROM games 
            WHERE start_time > NOW() 
            ORDER BY start_time ASC 
            LIMIT 1
        """)
        game = cursor.fetchone()
        
        if not game:
            return ERROR_MESSAGES["no_upcoming_game"]
            
        game_id = game['id']
        
        # 3. Upsert Response
        cursor.execute("""
            INSERT INTO game_responses (game_id, player_id, status, updated_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT (game_id, player_id) 
            DO UPDATE SET status = EXCLUDED.status, updated_at = NOW()
        """, (game_id, player_id, status.lower()))
        
        conn.commit()
        
        # Return a natural confirmation (agent will relay this)
        status_messages = {
            'confirmed': f"Got it! {player_name} is in for {game['start_time']}.",
            'declined': f"No worries, marked {player_name} as can't make it.",
            'maybe': f"Cool, {player_name} is a maybe for now.",
            'pending': f"Updated {player_name}'s status to pending."
        }
        
        return status_messages.get(status.lower(), f"Updated {player_name}'s status to {status}.")
        
    except Exception as e:
        print(f"Error logging response: {e}")
        conn.rollback()
        return ERROR_MESSAGES["database_error"]
    finally:
        if conn:
            conn.close()

# List of tools available to the agent
tools = [get_game_details, check_availability, log_response]

# 3. Define State
class AgentState(TypedDict):
    messages: List[BaseMessage]

# 4. Create Agent with improved system prompt
agent_executor = create_react_agent(llm, tools, prompt=AGENT_SYSTEM_PROMPT)

# 5. Execution / Testing
if __name__ == "__main__":
    print("Running agent test...")
    user_input = "Hey, I'm in for the next game!"
    
    events = agent_executor.stream(
        {"messages": [("user", user_input)]},
        stream_mode="values"
    )
    
    for event in events:
        if "messages" in event:
            last_msg = event["messages"][-1]
            print(f"[{last_msg.type}]: {last_msg.content}")

