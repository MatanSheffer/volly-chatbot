import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv
from phone_utils import normalize_phone_number

load_dotenv()

def get_db_connection():
    """
    Establishes and returns a connection to the PostgreSQL database.
    Returns a connection object that should be closed after use.
    """
    try:
        conn = psycopg2.connect(
            user=os.environ.get("user"),
            password=os.environ.get("password"),
            host=os.environ.get("host"),
            port=os.environ.get("port"),
            dbname=os.environ.get("dbname")
        )
        return conn
    except Exception as e:
        print(f"Error connecting to database: {e}")
        raise e

def create_game(start_time: str, location: str = "Beach Court 1", max_players: int = 4):
    """Creates a new game in the database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            INSERT INTO games (start_time, location, max_players)
            VALUES (%s, %s, %s)
            RETURNING *
        """, (start_time, location, max_players))
        game = cursor.fetchone()
        conn.commit()
        return game
    except Exception as e:
        conn.rollback()
        print(f"Error creating game: {e}")
        return None
    finally:
        conn.close()

def get_active_players():
    """Retrieves all active players from the database."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("SELECT * FROM players WHERE active = TRUE")
        players = cursor.fetchall()
        return players
    except Exception as e:
        print(f"Error fetching players: {e}")
        return []
    finally:
        conn.close()

def get_player_by_phone(phone_number: str, country: str = "Israel"):
    """
    Retrieves a player by their phone number.
    Handles phone number normalization internally.
    
    Args:
        phone_number: Phone number in any format
        country: Country for normalization rules
        
    Returns:
        Player dict if found, None otherwise
    """
    normalized_phone = normalize_phone_number(phone_number, country)
    
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # Try exact match first
        cursor.execute("SELECT * FROM players WHERE phone_number = %s", (normalized_phone,))
        player = cursor.fetchone()
        
        if player:
            return player
            
        # If not found, try other common formats
        # This helps with data inconsistency
        alternate_formats = [
            phone_number,  # Original format
            "0" + normalized_phone[3:] if normalized_phone.startswith("972") else normalized_phone,  # Israeli local format
        ]
        
        for alt_phone in alternate_formats:
            cursor.execute("SELECT * FROM players WHERE phone_number = %s", (alt_phone,))
            player = cursor.fetchone()
            if player:
                return player
        
        return None
    except Exception as e:
        print(f"Error fetching player by phone: {e}")
        return None
    finally:
        conn.close()

def get_player_game_status(phone_number: str, game_id=None):
    """
    Gets a player's response status for a specific game (or the next game).
    
    Args:
        phone_number: Player's phone number
        game_id: Specific game ID, or None for next upcoming game
        
    Returns:
        Dict with game info and player's status, or None if not found
    """
    player = get_player_by_phone(phone_number)
    if not player:
        return None
        
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        # If no game_id specified, get next upcoming game
        if game_id is None:
            cursor.execute("""
                SELECT id, start_time, location, max_players FROM games 
                WHERE start_time > NOW() 
                ORDER BY start_time ASC 
                LIMIT 1
            """)
            game = cursor.fetchone()
            if not game:
                return {"error": "No upcoming games"}
            game_id = game['id']
        else:
            cursor.execute("""
                SELECT id, start_time, location, max_players FROM games 
                WHERE id = %s
            """, (game_id,))
            game = cursor.fetchone()
            if not game:
                return {"error": "Game not found"}
        
        # Get player's response status
        cursor.execute("""
            SELECT status, updated_at FROM game_responses
            WHERE game_id = %s AND player_id = %s
        """, (game_id, player['id']))
        
        response = cursor.fetchone()
        
        return {
            "player_name": player['name'],
            "player_id": player['id'],
            "game_id": game['id'],
            "game_time": game['start_time'],
            "game_location": game['location'],
            "max_players": game['max_players'],
            "status": response['status'] if response else 'pending',
            "updated_at": response['updated_at'] if response else None
        }
        
    except Exception as e:
        print(f"Error fetching player game status: {e}")
        return None
    finally:
        conn.close()

def add_message_to_history(phone_number: str, role: str, content: str):
    """Adds a message to the conversation history."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO conversation_history (phone_number, role, content)
            VALUES (%s, %s, %s)
        """, (phone_number, role, content))
        conn.commit()
    except Exception as e:
        print(f"Error adding message to history: {e}")
    finally:
        conn.close()

def get_conversation_history(phone_number: str, limit: int = 10):
    """Retrieves the last N messages for a phone number."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute("""
            SELECT role, content FROM conversation_history
            WHERE phone_number = %s
            ORDER BY created_at DESC
            LIMIT %s
        """, (phone_number, limit))
        return cursor.fetchall()[::-1]
    except Exception as e:
        print(f"Error fetching history: {e}")
        return []
    finally:
        conn.close()

