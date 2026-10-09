"""Create MySQL connections from environment variables."""

import os


def get_db_connection():
    """Return a connection to the configured logistics database."""
    import mysql.connector
    from dotenv import load_dotenv

    load_dotenv()
    return mysql.connector.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", "3306")),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", ""),
        database=os.getenv("DB_NAME", "portfolio_logistics"),
        autocommit=False,
    )


if __name__ == "__main__":
    connection = get_db_connection()
    try:
        print("MySQL connection successful")
    finally:
        connection.close()
