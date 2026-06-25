import os
from core.server import start_server
from storage.db_client import init_db

def main():
    print("=" * 60)
    print("APEX FINANCIAL INTELLIGENCE DASHBOARD")
    print("=" * 60)

    # Initialize SQLite tables
    init_db()

    # Start the web server serving the dashboard
    print("\n" + "=" * 60)
    print("STARTING APEX FINANCIAL INTELLIGENCE SERVER")
    print("=" * 60)
    start_server()

if __name__ == "__main__":
    main()
