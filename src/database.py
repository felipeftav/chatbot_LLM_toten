"""Gerenciamento de conexões e registros no PostgreSQL."""

from datetime import datetime
import pytz
import psycopg2
from psycopg2 import pool
from src.config import DATABASE_URL

db_pool = None

if DATABASE_URL:
    try:
        db_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            dsn=DATABASE_URL,
            sslmode="require",
        )
        conn = db_pool.getconn()
        with conn.cursor() as cursor:
            cursor.execute("SELECT version();")
            pg_version = cursor.fetchone()[0]
            print(f"✅ Conexão com pool estabelecida! PostgreSQL: {pg_version}")
        db_pool.putconn(conn)
    except Exception as e:
        print(f"❌ Erro ao criar pool de conexões: {e}")
        db_pool = None
else:
    print("ℹ️ DATABASE_URL não encontrada ou desativada. Logs em banco desabilitados.")


def log_message(sender: str, message_text: str, profile_data: dict = None) -> None:
    """Insere uma mensagem individual no banco usando pool de conexões."""
    if not db_pool:
        return

    profile = profile_data or {}
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_log (
                    id SERIAL PRIMARY KEY,
                    sender VARCHAR(10) NOT NULL,
                    message TEXT NOT NULL,
                    user_name VARCHAR(100),
                    role VARCHAR(50),
                    interest_area VARCHAR(100),
                    objective VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE,
                    created_at_sp_str VARCHAR(25)
                );
                """
            )
            sp_tz = pytz.timezone("America/Sao_Paulo")
            timestamp_sp = datetime.now(sp_tz)
            timestamp_sp_str = timestamp_sp.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                INSERT INTO chat_log 
                    (sender, message, user_name, role, interest_area, objective, created_at, created_at_sp_str) 
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    sender,
                    message_text,
                    profile.get("name", ""),
                    profile.get("role", ""),
                    profile.get("interestArea", ""),
                    profile.get("objective", ""),
                    timestamp_sp,
                    timestamp_sp_str,
                ),
            )
        conn.commit()
    except Exception as e:
        print(f"❌ Erro ao salvar mensagem no log: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn and db_pool:
            db_pool.putconn(conn)


def log_interaction(user_message: str, bot_reply: str, profile_data: dict = None) -> None:
    """Salva a interação completa (usuário + bot) usando pool de conexões."""
    if not db_pool:
        return

    profile = profile_data or {}
    conn = None
    try:
        conn = db_pool.getconn()
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS chat_interactions (
                    id SERIAL PRIMARY KEY,
                    user_message TEXT,
                    bot_reply TEXT,
                    user_name VARCHAR(100),
                    role VARCHAR(50),
                    interest_area VARCHAR(100),
                    objective VARCHAR(100),
                    created_at TIMESTAMP WITH TIME ZONE,
                    created_at_sp_str VARCHAR(25)
                );
                """
            )
            sp_tz = pytz.timezone("America/Sao_Paulo")
            timestamp_sp = datetime.now(sp_tz)
            timestamp_sp_str = timestamp_sp.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                INSERT INTO chat_interactions 
                    (user_message, bot_reply, user_name, role, interest_area, objective, created_at, created_at_sp_str)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
                """,
                (
                    user_message,
                    bot_reply,
                    profile.get("name", ""),
                    profile.get("role", ""),
                    profile.get("interestArea", ""),
                    profile.get("objective", ""),
                    timestamp_sp,
                    timestamp_sp_str,
                ),
            )
        conn.commit()
        print("💾 Interação (usuário + bot) salva com sucesso!")
    except Exception as e:
        print(f"❌ Erro ao salvar interação: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn and db_pool:
            db_pool.putconn(conn)
