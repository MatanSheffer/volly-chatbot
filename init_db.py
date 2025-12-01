from database import get_db_connection

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("Creating tables...")

    # Enable UUID extension
    cursor.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')

    # 1. Create players table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS players (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name TEXT NOT NULL,
            phone_number TEXT UNIQUE NOT NULL,
            skill_level TEXT DEFAULT 'Intermediate',
            active BOOLEAN DEFAULT TRUE,
            language TEXT DEFAULT 'English',
            country TEXT DEFAULT 'Israel',
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # 2. Create games table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS games (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            start_time TIMESTAMPTZ NOT NULL,
            location TEXT DEFAULT 'Beach Court 1',
            status TEXT DEFAULT 'recruiting',
            max_players INTEGER DEFAULT 4,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    # 3. Create game_responses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS game_responses (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            game_id UUID REFERENCES games(id) ON DELETE CASCADE,
            player_id UUID REFERENCES players(id) ON DELETE CASCADE,
            status TEXT DEFAULT 'pending',
            original_message TEXT,
            ai_confidence FLOAT,
            updated_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(game_id, player_id)
        );
    """)

    # 4. Create conversation_history table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversation_history (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            phone_number TEXT NOT NULL,
            role TEXT NOT NULL, -- 'user' or 'ai'
            content TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    conn.commit()
    cursor.close()
    conn.close()
    print("Tables created successfully!")

if __name__ == "__main__":
    init_db()
