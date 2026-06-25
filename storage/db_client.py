# Predefined corporate event types
INITIAL_EVENTS = [
    {"event_type": "earnings_report", "category": "financials", "description": "Official company earnings release and report."},
    {"event_type": "revenue_growth", "category": "financials", "description": "Increase in company quarterly or annual revenue."},
    {"event_type": "revenue_decline", "category": "financials", "description": "Decrease in company quarterly or annual revenue."},
    {"event_type": "profit_loss", "category": "financials", "description": "Information on net profits or losses."},
    {"event_type": "contract_win", "category": "business_operations", "description": "Securing a new client agreement, deal, or project contract."},
    {"event_type": "contract_loss", "category": "business_operations", "description": "Loss of an existing client contract, cancellation, or renewal failure."},
    {"event_type": "acquisition", "category": "corporate_strategy", "description": "Acquiring another company, asset, or division."},
    {"event_type": "merger", "category": "corporate_strategy", "description": "Merging with another business entity."},
    {"event_type": "partnership", "category": "corporate_strategy", "description": "Strategic alliance or partnership with another organization."},
    {"event_type": "leadership_change", "category": "corporate_governance", "description": "Change in C-level executives, board members, or key leadership roles."},
    {"event_type": "layoffs", "category": "employment", "description": "Reduction of workforce or employee layoffs."},
    {"event_type": "hiring_expansion", "category": "employment", "description": "Workforce hiring expansion or job growth campaigns."},
    {"event_type": "product_launch", "category": "product_tech", "description": "Launch of a new product, platform, or service."},
    {"event_type": "product_recall", "category": "product_tech", "description": "Recall of an existing product or service suspension."},
    {"event_type": "regulatory_issue", "category": "compliance", "description": "Regulatory investigations, violations, compliance issues, or fines."},
    {"event_type": "legal_case", "category": "compliance", "description": "Lawsuits, court rulings, or legal disputes."},
    {"event_type": "market_expansion", "category": "corporate_strategy", "description": "Entering a new geographic or business market sector."},
    {"event_type": "investment", "category": "corporate_strategy", "description": "CapEx, capital investment, or funding allocated for development."},
    {"event_type": "infrastructure_expansion", "category": "business_operations", "description": "Expansion of offices, data centers, facilities, or physical footprint."},
    {"event_type": "cybersecurity_incident", "category": "product_tech", "description": "Data breach, cyber attack, or system security compromise."}
]

# Predefined sector clusters for company health evaluation
INITIAL_CLUSTERS = [
    {"cluster_type": "financials", "category": "financial_performance", "description": "Measures of revenue growth, profit margins, costs, and cash flows."},
    {"cluster_type": "operations", "category": "business_operations", "description": "Operational efficiency, client contract wins, and physical footprint expansion."},
    {"cluster_type": "governance", "category": "corporate_governance", "description": "C-suite alignment, leadership transitions, and strategic corporate direction."},
    {"cluster_type": "employment", "category": "human_capital", "description": "Employee sentiment, hiring expansions, layoffs, and compensation adjustments."},
    {"cluster_type": "product_tech", "category": "technology_innovation", "description": "Software updates, agentic AI platforms, cloud solutions, and security posture."},
    {"cluster_type": "compliance", "category": "risk_compliance", "description": "Legal case developments, court trials, and government regulatory investigations."}
]

import sqlite3
import os

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "database.db")
_use_memory_db = False
_memory_conn = None

def get_connection():
    global _use_memory_db, _memory_conn
    if _use_memory_db:
        if _memory_conn is None:
            _memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
            init_db_conn(_memory_conn)
        return _memory_conn
    try:
        conn = sqlite3.connect(DB_FILE)
        # Test writeability
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS _test_write (id INTEGER PRIMARY KEY)")
        cursor.execute("DROP TABLE _test_write")
        conn.commit()
        return conn
    except sqlite3.OperationalError:
        print("[Database] Warning: SQLite database file is read-only or not writeable. Falling back to in-memory SQLite database for Vercel/stateless mode.")
        _use_memory_db = True
        _memory_conn = sqlite3.connect(":memory:", check_same_thread=False)
        init_db_conn(_memory_conn)
        return _memory_conn

def init_db_conn(conn):
    cursor = conn.cursor()
    
    # 1. Clusters table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clusters (
            cluster_type TEXT PRIMARY KEY,
            category TEXT,
            description TEXT
        )
    """)
    
    # 2. Event Types table (registry of events)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS event_types (
            event_type TEXT PRIMARY KEY,
            category TEXT,
            description TEXT
        )
    """)
    
    # 3. Articles table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS articles (
            article_id TEXT PRIMARY KEY,
            title TEXT,
            url TEXT,
            published_at TEXT,
            description TEXT
        )
    """)
    
    # 4. Events table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS events (
            event_id TEXT PRIMARY KEY,
            article_id TEXT,
            event_type TEXT,
            impact_area TEXT,
            direction TEXT,
            confidence REAL,
            summary TEXT,
            timestamp TEXT
        )
    """)
    
    # 5. Signals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            signal_id TEXT PRIMARY KEY,
            event_id TEXT,
            article_id TEXT,
            signal_type TEXT,
            cluster_type TEXT,
            strength REAL,
            decayed_strength REAL,
            persistence REAL,
            decay_rate REAL,
            relevance_score REAL,
            confidence REAL,
            timestamp TEXT
        )
    """)
    
    # Seed INITIAL_EVENTS and INITIAL_CLUSTERS if empty
    cursor.execute("SELECT COUNT(*) FROM event_types")
    if cursor.fetchone()[0] == 0:
        for ev in INITIAL_EVENTS:
            cursor.execute(
                "INSERT OR IGNORE INTO event_types (event_type, category, description) VALUES (?, ?, ?)",
                (ev["event_type"], ev["category"], ev["description"])
            )
            
    cursor.execute("SELECT COUNT(*) FROM clusters")
    if cursor.fetchone()[0] == 0:
        for cl in INITIAL_CLUSTERS:
            cursor.execute(
                "INSERT OR IGNORE INTO clusters (cluster_type, category, description) VALUES (?, ?, ?)",
                (cl["cluster_type"], cl["category"], cl["description"])
            )
            
    conn.commit()

def init_db():
    try:
        conn = get_connection()
        if not _use_memory_db:
            init_db_conn(conn)
            conn.close()
    except Exception as e:
        print(f"[Database Error] Failed to initialize file database: {e}. Fallback to in-memory.")

def add_cluster(cluster_type, category, description):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO clusters (cluster_type, category, description) VALUES (?, ?, ?)",
            (cluster_type, category, description)
        )
        conn.commit()
        if not _use_memory_db:
            conn.close()
    except Exception as e:
        print(f"[Database Error] add_cluster failed: {e}")

def get_clusters():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT cluster_type, category, description FROM clusters")
        rows = cursor.fetchall()
        if not _use_memory_db:
            conn.close()
        return [{"cluster_type": r[0], "category": r[1], "description": r[2]} for r in rows]
    except Exception as e:
        print(f"[Database Error] get_clusters failed: {e}")
        return []

def add_event_type(event_type, category, description):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO event_types (event_type, category, description) VALUES (?, ?, ?)",
            (event_type, category, description)
        )
        conn.commit()
        if not _use_memory_db:
            conn.close()
    except Exception as e:
        print(f"[Database Error] add_event_type failed: {e}")

def get_event_types():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT event_type, category, description FROM event_types")
        rows = cursor.fetchall()
        if not _use_memory_db:
            conn.close()
        return [{"event_type": r[0], "category": r[1], "description": r[2]} for r in rows]
    except Exception as e:
        print(f"[Database Error] get_event_types failed: {e}")
        return []

def add_article(article):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO articles (article_id, title, url, published_at, description) VALUES (?, ?, ?, ?, ?)",
            (article.get("article_id"), article.get("title"), article.get("url"), article.get("published_at"), article.get("description"))
        )
        conn.commit()
        if not _use_memory_db:
            conn.close()
    except Exception as e:
        print(f"[Database Error] add_article failed: {e}")

def get_articles():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT article_id, title, url, published_at, description FROM articles")
        rows = cursor.fetchall()
        if not _use_memory_db:
            conn.close()
        return [{"article_id": r[0], "title": r[1], "url": r[2], "published_at": r[3], "description": r[4]} for r in rows]
    except Exception as e:
        print(f"[Database Error] get_articles failed: {e}")
        return []

def add_event(event):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO events (event_id, article_id, event_type, impact_area, direction, confidence, summary, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (event.get("event_id"), event.get("article_id"), event.get("event_type"), event.get("impact_area"), event.get("direction"), event.get("confidence"), event.get("summary"), event.get("timestamp"))
        )
        conn.commit()
        if not _use_memory_db:
            conn.close()
    except Exception as e:
        print(f"[Database Error] add_event failed: {e}")

def get_events():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT event_id, article_id, event_type, impact_area, direction, confidence, summary, timestamp FROM events")
        rows = cursor.fetchall()
        if not _use_memory_db:
            conn.close()
        return [{
            "event_id": r[0],
            "article_id": r[1],
            "event_type": r[2],
            "impact_area": r[3],
            "direction": r[4],
            "confidence": r[5],
            "summary": r[6],
            "timestamp": r[7]
        } for r in rows]
    except Exception as e:
        print(f"[Database Error] get_events failed: {e}")
        return []

def add_signal(signal):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO signals (signal_id, event_id, article_id, signal_type, cluster_type, strength, decayed_strength, persistence, decay_rate, relevance_score, confidence, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (signal.get("signal_id"), signal.get("event_id"), signal.get("article_id"), signal.get("signal_type"), signal.get("cluster_type"), signal.get("strength"), signal.get("decayed_strength"), signal.get("persistence"), signal.get("decay_rate"), signal.get("relevance_score"), signal.get("confidence"), signal.get("timestamp"))
        )
        conn.commit()
        if not _use_memory_db:
            conn.close()
    except Exception as e:
        print(f"[Database Error] add_signal failed: {e}")

def get_signals():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT signal_id, event_id, article_id, signal_type, cluster_type, strength, decayed_strength, persistence, decay_rate, relevance_score, confidence, timestamp FROM signals")
        rows = cursor.fetchall()
        if not _use_memory_db:
            conn.close()
        return [{
            "signal_id": r[0],
            "event_id": r[1],
            "article_id": r[2],
            "signal_type": r[3],
            "cluster_type": r[4],
            "strength": r[5],
            "decayed_strength": r[6],
            "persistence": r[7],
            "decay_rate": r[8],
            "relevance_score": r[9],
            "confidence": r[10],
            "timestamp": r[11]
        } for r in rows]
    except Exception as e:
        print(f"[Database Error] get_signals failed: {e}")
        return []

def clear_db():
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM articles")
        cursor.execute("DELETE FROM events")
        cursor.execute("DELETE FROM signals")
        conn.commit()
        if not _use_memory_db:
            conn.close()
        print("[Database] Successfully cleared articles, events, and signals.")
        return True
    except Exception as e:
        print(f"[Database Error] clear_db failed: {e}")
        return False

