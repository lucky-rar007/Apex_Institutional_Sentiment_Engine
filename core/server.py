import http.server
import socketserver
import json
import os
import re
import math
from datetime import datetime
from urllib.parse import urlparse, parse_qs

# Simple zero-dependency env loader
def load_env():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    parts = line.split("=", 1)
                    key = parts[0].strip()
                    value = parts[1].strip().strip("'\"")
                    os.environ[key] = value

load_env()

from core.pipeline import query_gemini_api

PORT = int(os.getenv("PORT", 8000))
FORCE_FALLBACK = False

# Pre-defined stock registry (alphabetically sorted)
STOCK_REGISTRY = [
    {"key": "AXISBNK", "name": "Axis Bank", "url": "https://www.moneycontrol.com/company-article/axisbank/news/AB16", "ticker": "AXISBNK.NS"},
    {"key": "BHARTIARTL", "name": "Bharti Airtel", "url": "https://www.moneycontrol.com/company-article/bhartiairtel/news/BA08", "ticker": "BHARTIARTL.NS"},
    {"key": "HDFCBANK", "name": "HDFC Bank", "url": "https://www.moneycontrol.com/company-article/hdfcbank/news/HDF01", "ticker": "HDFCBANK.NS"},
    {"key": "ICICIBANK", "name": "ICICI Bank", "url": "https://www.moneycontrol.com/company-article/icicibank/news/ICI02", "ticker": "ICICIBANK.NS"},
    {"key": "INFY", "name": "Infosys", "url": "https://www.moneycontrol.com/company-article/infosys/news/IT", "ticker": "INFY.NS"},
    {"key": "ITC", "name": "ITC", "url": "https://www.moneycontrol.com/company-article/itc/news/ITC", "ticker": "ITC.NS"},
    {"key": "LT", "name": "L&T", "url": "https://www.moneycontrol.com/company-article/larsentoubro/news/LT", "ticker": "LT.NS"},
    {"key": "RELIANCE", "name": "Reliance Industries", "url": "https://www.moneycontrol.com/company-article/relianceindustries/news/RI", "ticker": "RELIANCE.NS"},
    {"key": "SBIN", "name": "SBI", "url": "https://www.moneycontrol.com/company-article/statebankindia/news/SBI", "ticker": "SBIN.NS"},
    {"key": "TCS", "name": "TCS", "url": "https://www.moneycontrol.com/company-article/tataconsultancyservices/news/TCS", "ticker": "TCS.NS"}
]


def load_prompt_template(filename):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

# STRICT INPUT SANITIZATION & VALIDATORS
def sanitize_string(s):
    if s is None:
        return ""
    # Ensure it's treated as a string
    s_str = str(s)
    # Strip HTML tags
    clean = re.sub(r'<[^>]*>', '', s_str)
    # Escape basic special characters to prevent dynamic injection HTML-side
    clean = clean.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    return clean

def validate_url(url_str):
    if not url_str:
        return False, "URL cannot be empty."
    
    # Strip potential html/script tags
    sanitized = sanitize_string(url_str)
    if sanitized != url_str:
        return False, "HTML or script tags detected in URL."

    try:
        parsed = urlparse(url_str)
        if parsed.scheme != "https":
            return False, "URL protocol must be HTTPS."
        
        # Security validation: parsed.hostname checks the domain name without userinfo or ports
        hostname = parsed.hostname
        if hostname not in ("www.moneycontrol.com", "moneycontrol.com"):
            return False, "URL domain must be moneycontrol.com."
            
        # Security validation: reject query parameters or fragments to prevent dynamic payload injection
        if parsed.query or parsed.fragment:
            return False, "Query parameters and fragment identifiers are not allowed."
            
        # Block malicious characters in path (like script tags or backslashes)
        if re.search(r'[<>"\'()\{\}\[\];\\^`~]', parsed.path):
            return False, "Invalid/malicious characters detected in URL path."
        return True, None
    except Exception:
        return False, "Failed to parse URL."

def validate_date(date_str, allow_future=False):
    if not date_str:
        return False, "Date is required."
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # Check if date is in the future
        if not allow_future and dt > datetime.now():
            return False, "Cutoff date cannot be in the future."
        # Check if date is before year 2000
        if dt.year < 2000:
            return False, "Cutoff date cannot be earlier than the year 2000."
        return True, dt
    except ValueError:
        return False, "Invalid date format. Must be YYYY-MM-DD."

def validate_api_key(api_key):
    if not api_key:
        return False, "API key is required."
    api_key = api_key.strip()
    # Support alphanumeric, dashes, underscores, dots, slashes, plus, and equals signs (common in API keys/tokens)
    if not re.match(r'^[a-zA-Z0-9_\-\.\+\/=]+$', api_key):
        return False, "Invalid API key format. Key contains invalid characters."
    if len(api_key) < 10 or len(api_key) > 150:
        return False, "Invalid API key length."
    return True, None

def sanitize_signals(signals):
    sanitized = []
    if not isinstance(signals, list):
        return sanitized
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        try:
            sanitized.append({
                "signal_id": sanitize_string(str(sig.get("signal_id", ""))),
                "event_id": sanitize_string(str(sig.get("event_id", ""))),
                "article_id": sanitize_string(str(sig.get("article_id", ""))),
                "signal_type": sanitize_string(str(sig.get("signal_type", ""))),
                "cluster_type": sanitize_string(str(sig.get("cluster_type", ""))),
                "strength": float(sig.get("strength", 0.0)),
                "decayed_strength": float(sig.get("decayed_strength", 0.0)),
                "persistence": float(sig.get("persistence", 0.0)),
                "decay_rate": float(sig.get("decay_rate", 0.0)),
                "relevance_score": float(sig.get("relevance_score", 0.0)),
                "confidence": float(sig.get("confidence", 0.0)),
                "timestamp": sanitize_string(str(sig.get("timestamp", ""))),
                "event_summary": sanitize_string(str(sig.get("event_summary", ""))),
                "article_title": sanitize_string(str(sig.get("article_title", ""))),
                "article_url": sanitize_string(str(sig.get("article_url", "")))
            })
        except (ValueError, TypeError):
            continue
    return sanitized

def evaluate_sectors_in_memory(signals, api_key):
    """
    Stateless evaluator: processes sector health in-memory using Gemini.
    """
    from storage.db_client import get_clusters, INITIAL_CLUSTERS
    db_clusters = get_clusters()
    
    # 1. Initialize cluster dictionary from database or INITIAL_CLUSTERS fallback
    clusters = {cl["cluster_type"]: {"category": cl["category"], "description": cl["description"]} for cl in (db_clusters if db_clusters else INITIAL_CLUSTERS)}
    
    # 2. Group signals by cluster_type for traceability mapping
    cluster_signals_map = {c_type: [] for c_type in clusters.keys()}
    
    # Scan signals for any newly proposed clusters not in INITIAL_CLUSTERS, and enrich maps
    for s in signals:
        c_type = s["cluster_type"]
        if not c_type:
            continue
        if c_type not in clusters:
            clusters[c_type] = {
                "category": "general",
                "description": f"Dynamically clustered events for {c_type.replace('_', ' ').title()}"
            }
            cluster_signals_map[c_type] = []
            
        formatted_sig = {
            "signal_id": s["signal_id"],
            "type": s["signal_type"],
            "strength": s["strength"],
            "decayed_strength": s["decayed_strength"],
            "relevance": s["relevance_score"],
            "confidence": s["confidence"],
            "date": s["timestamp"],
            "summary": s.get("event_summary", "N/A"),
            "article_title": s.get("article_title", "N/A"),
            "article_url": s.get("article_url", "#")
        }
        cluster_signals_map[c_type].append(formatted_sig)
        
    # 3. Formulate the evaluation prompt
    health_template = load_prompt_template("gemini_sector_health_prompt.txt")
    
    sectors_data = []
    for c_type, info in clusters.items():
        sectors_data.append({
            "cluster_type": c_type,
            "description": info.get("description", ""),
            "category": info.get("category", "")
        })
        
    signals_data = []
    for s in signals:
        signals_data.append({
            "id": s["signal_id"],
            "cluster_type": s["cluster_type"],
            "decayed_strength": s["decayed_strength"],
            "relevance": s["relevance_score"],
            "confidence": s["confidence"],
            "summary": s.get("event_summary", "N/A"),
            "date": s["timestamp"]
        })
        
    prompt = health_template.format(
        sectors_json=json.dumps(sectors_data, indent=2),
        signals_json=json.dumps(signals_data, indent=2)
    )
    
    global FORCE_FALLBACK
    if FORCE_FALLBACK:
        dashboard_model = "gemini-3.1-flash-lite"
        print("[Server] Bypassing primary model due to active rate-limit block. Querying with fallback model...")
    else:
        dashboard_model = os.getenv("DASHBOARD_GEMINI_MODEL", "gemini-3.5-flash")
        
    eval_data = {}
    
    try:
        # Re-check flag right before call (another thread may have set it in the meantime)
        if FORCE_FALLBACK and dashboard_model != "gemini-3.1-flash-lite":
            dashboard_model = "gemini-3.1-flash-lite"
            print("[Server] FORCE_FALLBACK activated by another thread. Switching to fallback model.")
        print(f"[Server] Requesting consolidated safety evaluation using '{dashboard_model}'...")
        res_str = query_gemini_api(prompt, model_name=dashboard_model, api_key=api_key)
        eval_data = json.loads(res_str).get("evaluations", {})
    except Exception as e:
        print(f"[Server Warning] Failed using model '{dashboard_model}': {str(e)}")
        # If rate limited (HTTP 429), enable global FORCE_FALLBACK flag to directly use fallback for all other requests
        if "429" in str(e) or "rate limit" in str(e).lower() or "too many requests" in str(e).lower():
            print("[Server] Rate limit (429) detected. Activating FORCE_FALLBACK mode for all future evaluations in this session.")
            FORCE_FALLBACK = True

        fallback_model = "gemini-3.1-flash-lite"
        if dashboard_model != fallback_model:
            try:
                print(f"[Server Fallback] Querying with '{fallback_model}'...")
                res_str = query_gemini_api(prompt, model_name=fallback_model, api_key=api_key)
                eval_data = json.loads(res_str).get("evaluations", {})
            except Exception as e_fallback:
                print(f"[Server Error] Fallback also failed: {str(e_fallback)}")
                
    # Map sector evaluations to output structure
    dashboard_sectors = {}
    for c_type, cluster_info in clusters.items():
        sigs = cluster_signals_map.get(c_type, [])
        
        health_score = 50
        status = "Stable"
        confidence = 1.0
        summary = "No signals have been recorded for this sector yet."
        
        if c_type in eval_data:
            sec_eval = eval_data[c_type]
            health_score = int(sec_eval.get("health_score", 50))
            status = sec_eval.get("status", "Stable")
            confidence = float(sec_eval.get("confidence", 1.0))
            summary = sec_eval.get("summary", "")
        elif sigs:
            health_score = 50
            status = "Stable"
            confidence = 0.5
            summary = "Safety evaluation failed. Showing baseline defaults."
            
        dashboard_sectors[c_type] = {
            "name": c_type.replace("_", " ").title(),
            "description": cluster_info["description"],
            "category": cluster_info["category"],
            "health_score": health_score,
            "status": status,
            "confidence": confidence,
            "summary": summary,
            "signals": sigs
        }
        
    return dashboard_sectors


class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    """
    Built-in HTTP server request handler.
    Serves static HTML/CSS/JS dashboard files and answers API requests dynamically.
    No SQLite storage dependency.
    """
    def end_headers(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-XSS-Protection", "1; mode=block")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com https://cdn.jsdelivr.net; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net; font-src https://fonts.gstatic.com; connect-src 'self' https://*.google-analytics.com https://*.analytics.google.com https://*.googletagmanager.com; img-src 'self' data: https:;")
        super().end_headers()

    def do_GET(self):
        if self.path == "/api/stocks":
            self.send_json_response(200, {"success": True, "stocks": STOCK_REGISTRY})
        elif self.path == "/api/signals":
            from storage.db_client import get_signals
            self.send_json_response(200, get_signals())
        elif self.path == "/api/events":
            from storage.db_client import get_events
            self.send_json_response(200, get_events())
        elif self.path == "/api/clusters":
            from storage.db_client import get_clusters
            self.send_json_response(200, get_clusters())
        elif self.path == "/api/articles":
            from storage.db_client import get_articles
            self.send_json_response(200, get_articles())
        elif self.path == "/api/event-types":
            from storage.db_client import get_event_types
            self.send_json_response(200, get_event_types())
        else:
            # Simply serve static files
            super().do_GET()

    def do_POST(self):
        if self.path == "/api/verify-link":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                url = req_json.get("url", "").strip()
                
                valid, err_msg = validate_url(url)
                if not valid:
                    self.send_json_response(400, {"success": False, "error": err_msg})
                    return
                
                from scraper.tag_scraper import scrape_articles_until_date
                # Try to scrape just first page without cutoff to see if it works
                scraped = scrape_articles_until_date(url, cutoff_dt=None, max_pages=1)
                
                self.send_json_response(200, {
                    "success": True, 
                    "article_count": len(scraped),
                    "message": f"Successfully verified page. Found {len(scraped)} articles."
                })
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": f"Failed to verify URL: {str(e)}"})
                
        elif self.path == "/api/verify-key":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                
                api_key = req_json.get("gemini_api_key", "").strip()
                
                key_valid, key_err = validate_api_key(api_key)
                if not key_valid:
                    self.send_json_response(400, {"success": False, "error": key_err})
                    return
                
                if api_key.startswith("AIzaSyMock"):
                    self.send_json_response(200, {"success": True, "message": "Mock API key verified successfully."})
                    return

                import requests
                url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
                resp = requests.get(url, timeout=10)
                
                if resp.status_code == 200:
                    self.send_json_response(200, {"success": True, "message": "API key is valid."})
                else:
                    try:
                        err_payload = resp.json()
                        err_msg = err_payload.get("error", {}).get("message", "API key verification failed.")
                    except:
                        err_msg = f"HTTP {resp.status_code}: Key verification failed."
                    self.send_json_response(400, {"success": False, "error": err_msg})
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": f"Failed to verify API key: {str(e)}"})
                
        elif self.path == "/api/run-pipeline":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                
                url = req_json.get("url", "").strip()
                cutoff_str = req_json.get("cutoff_date", "").strip()
                api_key = req_json.get("gemini_api_key", "").strip()
                
                # Validation
                url_valid, url_err = validate_url(url)
                if not url_valid:
                    self.send_json_response(400, {"success": False, "error": url_err})
                    return
                
                date_valid, date_result = validate_date(cutoff_str)
                if not date_valid:
                    self.send_json_response(400, {"success": False, "error": date_result})
                    return
                cutoff_dt = date_result
                
                key_valid, key_err = validate_api_key(api_key)
                if not key_valid:
                    self.send_json_response(400, {"success": False, "error": key_err})
                    return
                
                from core.pipeline import run_batch_pipeline
                result_state = run_batch_pipeline(url, cutoff_dt, api_key)
                
                self.send_json_response(200, {
                    "success": True,
                    "articles": result_state["articles"],
                    "events": result_state["events"],
                    "signals": result_state["signals"],
                    "registry": result_state["registry"],
                    "message": "Pipeline execution completed."
                })
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": f"Pipeline execution failed: {str(e)}"})
                
        elif self.path == "/api/evaluate-sectors":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                
                signals = req_json.get("signals", [])
                api_key = req_json.get("gemini_api_key", "").strip()
                
                # Validation
                key_valid, key_err = validate_api_key(api_key)
                if not key_valid:
                    self.send_json_response(400, {"success": False, "error": key_err})
                    return
                
                # Sanitize signals list
                sanitized_signals = sanitize_signals(signals)
                
                evaluations = evaluate_sectors_in_memory(sanitized_signals, api_key)
                
                self.send_json_response(200, {
                    "success": True,
                    "evaluations": evaluations
                })
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": f"Failed to evaluate sectors: {str(e)}"})
        elif self.path == "/api/clusters":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                
                c_type = sanitize_string(req_json.get("cluster_type", "").strip())
                cat = sanitize_string(req_json.get("category", "").strip())
                desc = sanitize_string(req_json.get("description", "").strip())
                
                if not c_type:
                    self.send_json_response(400, {"success": False, "error": "cluster_type is required."})
                    return
                    
                from storage.db_client import add_cluster
                add_cluster(c_type, cat, desc)
                self.send_json_response(200, {"success": True, "message": "Cluster added successfully."})
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
        elif self.path == "/api/events":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                
                event_dict = {
                    "event_id": sanitize_string(req_json.get("event_id", "").strip()),
                    "article_id": sanitize_string(req_json.get("article_id", "").strip()),
                    "event_type": sanitize_string(req_json.get("event_type", "").strip()),
                    "impact_area": sanitize_string(req_json.get("impact_area", "").strip()),
                    "direction": sanitize_string(req_json.get("direction", "neutral").strip()),
                    "confidence": float(req_json.get("confidence", 1.0)),
                    "summary": sanitize_string(req_json.get("summary", "").strip()),
                    "timestamp": sanitize_string(req_json.get("timestamp", "").strip())
                }
                
                if not event_dict["event_id"]:
                    self.send_json_response(400, {"success": False, "error": "event_id is required."})
                    return
                    
                from storage.db_client import add_event
                add_event(event_dict)
                self.send_json_response(200, {"success": True, "message": "Event added successfully."})
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
        elif self.path == "/api/signals":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                
                signal_dict = {
                    "signal_id": sanitize_string(req_json.get("signal_id", "").strip()),
                    "event_id": sanitize_string(req_json.get("event_id", "").strip()),
                    "article_id": sanitize_string(req_json.get("article_id", "").strip()),
                    "signal_type": sanitize_string(req_json.get("signal_type", "").strip()),
                    "cluster_type": sanitize_string(req_json.get("cluster_type", "").strip()),
                    "strength": float(req_json.get("strength", 0.0)),
                    "decayed_strength": float(req_json.get("decayed_strength", 0.0)),
                    "persistence": float(req_json.get("persistence", 0.0)),
                    "decay_rate": float(req_json.get("decay_rate", 0.0)),
                    "relevance_score": float(req_json.get("relevance_score", 0.0)),
                    "confidence": float(req_json.get("confidence", 0.0)),
                    "timestamp": sanitize_string(req_json.get("timestamp", "").strip())
                }
                
                if not signal_dict["signal_id"]:
                    self.send_json_response(400, {"success": False, "error": "signal_id is required."})
                    return
                    
                from storage.db_client import add_signal
                add_signal(signal_dict)
                self.send_json_response(200, {"success": True, "message": "Signal added successfully."})
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
        elif self.path == "/api/reset":
            try:
                from storage.db_client import clear_db
                success = clear_db()
                if success:
                    self.send_json_response(200, {"success": True, "message": "Database reset successfully."})
                else:
                    self.send_json_response(500, {"success": False, "error": "Failed to clear database."})
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": str(e)})
        elif self.path == "/api/stock-prices":
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                req_json = json.loads(post_data.decode('utf-8'))
                
                ticker = sanitize_string(req_json.get("ticker", "").strip())
                start_date = req_json.get("start_date", "").strip()
                end_date = req_json.get("end_date", "").strip()
                
                # Validate ticker is from our registry
                valid_tickers = [s["ticker"] for s in STOCK_REGISTRY]
                if ticker not in valid_tickers:
                    self.send_json_response(400, {"success": False, "error": "Invalid ticker symbol."})
                    return
                
                date_valid_s, _ = validate_date(start_date)
                date_valid_e, _ = validate_date(end_date, allow_future=True)
                if not date_valid_s or not date_valid_e:
                    self.send_json_response(400, {"success": False, "error": "Invalid date range."})
                    return
                
                import yfinance as yf
                stock = yf.Ticker(ticker)
                hist = stock.history(start=start_date, end=end_date)
                
                prices = []
                for date_idx, row in hist.iterrows():
                    prices.append({
                        "date": date_idx.strftime("%Y-%m-%d"),
                        "close": round(float(row["Close"]), 2)
                    })
                
                self.send_json_response(200, {"success": True, "prices": prices})
            except Exception as e:
                self.send_json_response(500, {"success": False, "error": f"Failed to fetch stock prices: {str(e)}"})
        else:
            self.send_response(404)
            self.end_headers()


    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def translate_path(self, path):
        # Resolve dashboard files relative to /dashboard directory under project root
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        dashboard_dir = os.path.abspath(os.path.join(root_dir, "dashboard"))
        
        # Strip queries or hashes
        clean_path = path.split('?', 1)[0].split('#', 1)[0]
        
        # Default index.html mapping
        if clean_path == "/" or not clean_path:
            return os.path.join(dashboard_dir, "index.html")
            
        rel_path = clean_path.lstrip('/')
        target_path = os.path.abspath(os.path.join(dashboard_dir, rel_path))
        
        # Security: Prevent Directory Traversal Vulnerability (Windows case-insensitive check)
        if not target_path.lower().startswith(dashboard_dir.lower()):
            return os.path.join(dashboard_dir, "index.html")
            
        return target_path


def start_server():
    """
    Launches ThreadingTCPServer on PORT 8000.
    """
    socketserver.ThreadingTCPServer.allow_reuse_address = True
    handler = DashboardHandler
    with socketserver.ThreadingTCPServer(("", PORT), handler) as httpd:
        print(f"\n[Server] Dashboard server running at: http://localhost:{PORT}/")
        print("[Server] Press Ctrl+C to stop the server.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Server] Dashboard server stopped.")
            httpd.shutdown()

if __name__ == "__main__":
    start_server()
