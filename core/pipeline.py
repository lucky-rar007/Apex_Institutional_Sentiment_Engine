import hashlib
import gc
import time
import os
import uuid
import requests
import json
from datetime import datetime
from scraper.article_scraper import fetch_article_text
from registry.event_matcher import match_and_register_event
from core.signal_generator import calculate_time_decay
from scraper.tag_scraper import scrape_articles_until_date

def calculate_article_id(url):
    """
    Generates a unique MD5 hash of the URL to serve as the article_id.
    """
    return hashlib.md5(url.encode('utf-8')).hexdigest()

# Global tracking for rate limiting (staying safely under 15 RPM for free tier)
_last_request_time = 0.0

def query_gemini_api(prompt, model_name=None, api_key=None):
    """
    Sends the prompt to Gemini using standard HTTP requests.
    Forces JSON response mode.
    Includes rate-limiting throttle (min 4.5s spacing) and exponential backoff on HTTP 429/503.
    """
    global _last_request_time
    import random
    
    if not api_key:
        api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Gemini API Key is missing. Please provide it in the input.")

    # Intercept mock keys for offline simulation
    if api_key.startswith("AIzaSyMock"):
        print(f"[Gemini Mock API] Intercepted mock key. Prompt length: {len(prompt)}")
        # Determine prompt type and return simulated JSON
        if "registry_json" in prompt:
            # Event extraction prompt
            # Extract first few article IDs from prompt to make mock data trace correctly
            import re
            art_ids = re.findall(r'"id":\s*"([^"]+)"', prompt)
            if not art_ids:
                art_ids = ["art_mock_1", "art_mock_2"]
            events_list = []
            for idx, a_id in enumerate(art_ids):
                # alternate between earnings and regulatory issues for variety
                if idx % 2 == 0:
                    events_list.append({
                        "article_id": a_id,
                        "event_type": "earnings_report",
                        "impact_area": "financials",
                        "direction": "positive",
                        "confidence": 0.95,
                        "summary": "Strong quarterly performance and revenue growth."
                    })
                else:
                    events_list.append({
                        "article_id": a_id,
                        "event_type": "regulatory_issue",
                        "impact_area": "compliance",
                        "direction": "negative",
                        "confidence": 0.80,
                        "summary": "Regulatory query regarding tax compliance."
                    })
            mock_res = {"events": events_list, "unknown_events": []}
            return json.dumps(mock_res)
            
        elif "events_json" in prompt:
            # Signal clustering prompt
            import re
            ev_matches = re.findall(r'"event_id":\s*"([^"]+)".*?"article_id":\s*"([^"]+)".*?"event_type":\s*"([^"]+)".*?"timestamp":\s*"([^"]+)"', prompt, re.DOTALL)
            if not ev_matches:
                # Try finding them individually
                ev_ids = re.findall(r'"event_id":\s*"([^"]+)"', prompt)
                art_ids = re.findall(r'"article_id":\s*"([^"]+)"', prompt)
                types = re.findall(r'"event_type":\s*"([^"]+)"', prompt)
                times = re.findall(r'"timestamp":\s*"([^"]+)"', prompt)
                ev_matches = list(zip(ev_ids, art_ids, types, times))
            
            signals_list = []
            for ev_id, a_id, ev_type, timestamp in ev_matches:
                strength = 2.5 if "earnings" in ev_type or "growth" in ev_type else -1.5
                cluster = "financials" if "earnings" in ev_type or "growth" in ev_type or "revenue" in ev_type else "compliance"
                signals_list.append({
                    "event_id": ev_id,
                    "article_id": a_id,
                    "signal_type": ev_type,
                    "cluster_type": cluster,
                    "strength": strength,
                    "relevance_score": 0.9,
                    "confidence": 0.95,
                    "timestamp": timestamp
                })
            if not signals_list:
                signals_list = [{
                    "event_id": "ev_mock",
                    "article_id": "art_mock",
                    "signal_type": "earnings_report",
                    "cluster_type": "financials",
                    "strength": 2.5,
                    "relevance_score": 0.9,
                    "confidence": 0.95,
                    "timestamp": "2026-06-25T10:00:00Z"
                }]
            mock_res = {"signals": signals_list}
            return json.dumps(mock_res)
            
        elif "sectors_json" in prompt:
            # Consolidated health evaluation
            mock_res = {
                "evaluations": {
                    "financials": {
                        "health_score": 85,
                        "status": "Healthy",
                        "confidence": 0.95,
                        "summary": "Outstanding operational and financial growth observed in recent reports."
                    },
                    "compliance": {
                        "health_score": 55,
                        "status": "Warning",
                        "confidence": 0.85,
                        "summary": "Pending regulatory inquiry resolved with minor administrative penalty."
                    },
                    "operations": {
                        "health_score": 75,
                        "status": "Stable",
                        "confidence": 0.90,
                        "summary": "Core operations are executing efficiently with steady expansion."
                    },
                    "governance": {
                        "health_score": 80,
                        "status": "Healthy",
                        "confidence": 0.95,
                        "summary": "Effective board alignment and clear strategic communication."
                    },
                    "employment": {
                        "health_score": 70,
                        "status": "Stable",
                        "confidence": 0.85,
                        "summary": "Staff satisfaction is stable with targeted key hire expansions."
                    },
                    "product_tech": {
                        "health_score": 82,
                        "status": "Healthy",
                        "confidence": 0.90,
                        "summary": "Strong software release cycle and robust security posture."
                    }
                }
            }
            return json.dumps(mock_res)
        else:
            return "{}"

    # Throttling: spacing requests to remain within RPM limits
    min_spacing = 2.0
    elapsed = time.time() - _last_request_time
    if elapsed < min_spacing:
        sleep_time = min_spacing - elapsed + random.uniform(0.1, 0.5)
        print(f"[Gemini Rate Limiter] Throttling request. Sleeping for {sleep_time:.2f}s...")
        time.sleep(sleep_time)

    if not model_name:
        model_name = os.getenv("PIPELINE_GEMINI_MODEL", os.getenv("GEMINI_MODEL_NAME", "gemini-3.1-flash-lite"))
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }
    
    headers = {"Content-Type": "application/json"}
    max_retries = 5
    base_backoff = 2.0
    
    for attempt in range(1, max_retries + 1):
        _last_request_time = time.time()
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=90)
            
            # Catch Rate Limits (429) or Temporary Service issues (503)
            if response.status_code in (429, 503):
                # Immediately broadcast rate-limit flag so other threads/requests skip the primary model
                if response.status_code == 429:
                    try:
                        import core.server as _srv
                        _srv.FORCE_FALLBACK = True
                        print("[Gemini Rate Limiter] Set FORCE_FALLBACK=True globally due to HTTP 429.")
                    except Exception:
                        pass
                backoff = (base_backoff ** attempt) + random.uniform(0.5, 1.5)
                print(f"[Gemini Rate Limiter] Received HTTP {response.status_code} (Attempt {attempt}/{max_retries}). Retrying in {backoff:.2f}s...")
                time.sleep(backoff)
                continue
                
            if response.status_code != 200:
                raise Exception(f"Gemini API returned error status {response.status_code}: {response.text}")
                
            res_data = response.json()
            content_text = res_data["candidates"][0]["content"]["parts"][0]["text"]
            return content_text
            
        except (requests.exceptions.RequestException, KeyError, IndexError) as e:
            if attempt == max_retries:
                raise Exception(f"Failed to query Gemini API after {max_retries} attempts: {str(e)}")
            
            backoff = (base_backoff ** attempt) + random.uniform(0.5, 1.5)
            print(f"[Gemini Rate Limiter] Error occurred: {str(e)} (Attempt {attempt}/{max_retries}). Retrying in {backoff:.2f}s...")
            time.sleep(backoff)

    raise Exception("Failed to query Gemini API after maximum retries.")

def load_prompt_template(filename):
    """
    Loads a raw prompt template text file from the project's prompts directory.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base_dir, "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def fetch_single_article(meta, idx, total, session=None):
    url = meta.get("link", "").strip()
    title = meta.get("title", "").strip()
    description = meta.get("description", "").strip()
    published_at = meta.get("date", "").strip()
    
    if not url:
        return None
        
    article_id = calculate_article_id(url)
    print(f"    [{idx}/{total}] Downloading text: {title[:50]}...")
    try:
        full_text = fetch_article_text(url, session=session)
        if full_text and len(full_text.strip()) > 100:
            print(f"      Scraped {len(full_text)} characters for: {title[:30]}...")
            return {
                "article_id": article_id,
                "title": title,
                "url": url,
                "published_at": published_at,
                "description": description,
                "text": full_text
            }
        else:
            print(f"      Scraped text too short or empty for: {title[:30]}...")
    except Exception as e:
        print(f"      Failed to scrape {title[:30]}: {str(e)}")
    return None

def run_gemini_batch_event_extraction(articles_metadata, api_key, registry, batch_size=10):
    """
    Downloads article full text and batches multiple articles in a single request to Gemini
    to extract corporate events and map them to the predefined taxonomy.
    Executes entirely in-memory.
    """
    print(f"\n[Pipeline] Preparing batch event extraction for {len(articles_metadata)} articles...")
    
    processed_articles = []
    total = len(articles_metadata)
    
    import concurrent.futures
    
    # Establish a Requests Session for connection pooling across threads
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    # Use ThreadPoolExecutor to download articles in parallel (20 concurrent threads)
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(fetch_single_article, meta, idx, total, session) for idx, meta in enumerate(articles_metadata, 1)]
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                processed_articles.append(result)

    if not processed_articles:
        print("[Pipeline] No articles were successfully scraped. Event extraction skipped.")
        return [], []
        
    extracted_events = []
    batch_prompt_template = load_prompt_template("gemini_batch_event_prompt.txt")
    
    for i in range(0, len(processed_articles), batch_size):
        batch = processed_articles[i:i + batch_size]
        print(f"\n[Pipeline] Processing Event Extraction Batch [{i+1}-{min(i+batch_size, len(processed_articles))}] via Gemini...")
        
        registry_list = []
        for ev_type, info in registry.items():
            registry_list.append({
                "event_type": ev_type,
                "category": info.get("category", "general"),
                "description": info.get("description", "")
            })
            
        formatted_articles_list = []
        for a in batch:
            formatted_articles_list.append({
                "id": a["article_id"],
                "title": a["title"],
                "description": a["description"],
                "published_at": a["published_at"],
                "text": a["text"][:12000] # Cap text length to prevent context explosion
            })
            
        prompt = batch_prompt_template.format(
            registry_json=json.dumps(registry_list, indent=2),
            articles_json=json.dumps(formatted_articles_list, indent=2)
        )
        
        try:
            raw_json_str = query_gemini_api(prompt, api_key=api_key)
            extracted_data = json.loads(raw_json_str)
        except Exception as e:
            print(f"    [Pipeline Error] Gemini batch extraction failed: {str(e)}")
            continue
            
        events = extracted_data.get("events", [])
        unknown_events = extracted_data.get("unknown_events", [])
        
        print(f"    [Pipeline] Gemini returned {len(events)} known and {len(unknown_events)} unknown events for batch.")
        
        # Process known events
        for idx, ev in enumerate(events, 1):
            a_id = ev["article_id"]
            event_type = ev["event_type"].strip().lower()
            
            # Verify event type exists or match/auto-register
            event_type = match_and_register_event(registry, event_type, "Auto-registered from batch mismatch", "general")
            
            event_id = f"ev_{a_id}_{idx}_{str(uuid.uuid4())[:4]}"
            pub_date = next((a["published_at"] for a in batch if a["article_id"] == a_id), datetime.now().isoformat())
            
            event_record = {
                "event_id": event_id,
                "article_id": a_id,
                "event_type": event_type,
                "impact_area": ev.get("impact_area", "general"),
                "direction": ev.get("direction", "neutral"),
                "confidence": float(ev.get("confidence", 1.0)),
                "summary": ev.get("summary", ""),
                "timestamp": pub_date
            }
            extracted_events.append(event_record)
            print(f"    [Event Saved] Type: {event_type} | Article: {a_id[:8]}... | Reason: {ev.get('summary')}")
            
        # Process unknown events
        for idx, uev in enumerate(unknown_events, len(events) + 1):
            a_id = uev["article_id"]
            proposed_name = uev["new_event_name"]
            desc = uev["description"]
            cat = uev["suggested_category"]
            confidence = float(uev.get("confidence", 1.0))
            
            resolved_type = match_and_register_event(
                registry=registry,
                proposed_type=proposed_name,
                description=desc,
                category=cat
            )
            
            event_id = f"ev_{a_id}_{idx}_{str(uuid.uuid4())[:4]}"
            pub_date = next((a["published_at"] for a in batch if a["article_id"] == a_id), datetime.now().isoformat())
            
            event_record = {
                "event_id": event_id,
                "article_id": a_id,
                "event_type": resolved_type,
                "impact_area": cat,
                "direction": "neutral",
                "confidence": confidence,
                "summary": desc,
                "timestamp": pub_date
            }
            extracted_events.append(event_record)
            print(f"    [Event Saved (New Registered)] Type: {resolved_type} | Article: {a_id[:8]}... | Reason: {desc}")
            
        # Release memory
        del prompt
        del extracted_data
        gc.collect()
        
    # Remove large text body from processed_articles returned to save space
    for a in processed_articles:
        if "text" in a:
            del a["text"]
            
    return processed_articles, extracted_events

def run_gemini_signals_clustering(events, api_key, cluster_registry, batch_size=50):
    """
    Groups events and runs signal clustering via Gemini.
    Executes entirely in-memory.
    """
    if not events:
        print("\n[Pipeline] No events found for signal clustering.")
        return [], cluster_registry
        
    print(f"\n[Pipeline] Batching {len(events)} events to Gemini for signal mapping...")
    template = load_prompt_template("gemini_signal_prompt.txt")
    generated_signals = []
    
    for i in range(0, len(events), batch_size):
        events_batch = events[i:i + batch_size]
        print(f"\n[Pipeline] Processing Signal Cluster Batch [{i+1}-{min(i+batch_size, len(events))}]...")
        
        re_run_batch = True
        attempts = 0
        
        while re_run_batch and attempts < 3:
            attempts += 1
            re_run_batch = False
            
            prompt = template.format(
                clusters_json=json.dumps(cluster_registry, indent=2),
                events_json=json.dumps(events_batch, indent=2)
            )
            
            try:
                raw_json_str = query_gemini_api(prompt, api_key=api_key)
                res_data = json.loads(raw_json_str)
                signals = res_data.get("signals", [])
            except Exception as e:
                print(f"    [Error] Gemini query failed on attempt {attempts}: {str(e)}")
                break
                
            # Check for new cluster proposals
            for sig in signals:
                cluster_type = sig.get("cluster_type", "").strip().lower()
                
                if cluster_type == "new_cluster_proposed":
                    proposed = sig.get("proposed_cluster", {})
                    new_cluster_name = proposed.get("cluster_name", "").strip().lower()
                    new_desc = proposed.get("description", "Dynamically proposed cluster").strip()
                    new_cat = proposed.get("category", "general").strip()
                    
                    try:
                        new_persistence = float(proposed.get("persistence", 0.6))
                    except (ValueError, TypeError):
                        new_persistence = 0.6
                        
                    try:
                        new_decay_rate = float(proposed.get("decay_rate", 0.02))
                    except (ValueError, TypeError):
                        new_decay_rate = 0.02
                    
                    if not new_cluster_name:
                        new_cluster_name = f"proposed_cluster_{str(uuid.uuid4())[:6]}"
                        
                    if new_cluster_name not in cluster_registry:
                        print(f"    [Registry] Gemini proposed new cluster '{new_cluster_name}'. Registering...")
                        cluster_registry[new_cluster_name] = {
                            "description": new_desc,
                            "category": new_cat,
                            "persistence": new_persistence,
                            "decay_rate": new_decay_rate
                        }
                        try:
                            from storage.db_client import add_cluster
                            add_cluster(new_cluster_name, new_cat, new_desc, new_persistence, new_decay_rate)
                        except Exception as e:
                            print(f"    [Registry Error] Failed to save new cluster to DB: {e}")
                        re_run_batch = True
                        break
                        
            if re_run_batch:
                print("    [Registry] Re-running batch with the updated cluster registry...")
                continue
                
            for sig in signals:
                event_id = sig["event_id"]
                article_id = sig["article_id"]
                signal_type = sig["signal_type"]
                cluster_type = sig["cluster_type"]
                strength = float(sig["strength"])
                relevance = float(sig["relevance_score"])
                confidence = float(sig["confidence"])
                timestamp = sig["timestamp"]
                
                c_info = cluster_registry.get(cluster_type, {})
                c_persistence = c_info.get("persistence", None)
                c_decay_rate = c_info.get("decay_rate", None)
                
                decayed_strength, persistence, decay_rate = calculate_time_decay(
                    strength=strength,
                    cluster_type=cluster_type,
                    timestamp_str=timestamp,
                    persistence=c_persistence,
                    decay_rate=c_decay_rate
                )
                
                signal_id = f"sig_{event_id}_{str(uuid.uuid4())[:8]}"
                
                generated_signals.append({
                    "signal_id": signal_id,
                    "event_id": event_id,
                    "article_id": article_id,
                    "signal_type": signal_type,
                    "cluster_type": cluster_type,
                    "strength": strength,
                    "decayed_strength": decayed_strength,
                    "persistence": persistence,
                    "decay_rate": decay_rate,
                    "relevance_score": relevance,
                    "confidence": confidence,
                    "timestamp": timestamp
                })
                print(f"    [Signal Mapped] Event: {event_id} -> Cluster: {cluster_type} | Strength: {strength} -> Decayed: {decayed_strength}")
                
            re_run_batch = False
            
    return generated_signals, cluster_registry

def run_batch_pipeline(start_url, cutoff_dt, api_key):
    """
    Stateless batch pipeline entrypoint.
    Returns the complete generated state JSON directly.
    """
    from storage.db_client import get_event_types, get_clusters, INITIAL_EVENTS, INITIAL_CLUSTERS
    
    print(f"\n[Pipeline] Starting in-memory unified batch pipeline execution for URL: {start_url}")
    start_time = time.time()
    
    # 1. Scrape metadata from Moneycontrol
    scraped_articles_meta = scrape_articles_until_date(start_url, cutoff_dt)
    
    # 2. Initialize in-memory registries from database
    db_events = get_event_types()
    db_clusters = get_clusters()
    
    event_registry = {ev["event_type"]: {"category": ev["category"], "description": ev["description"]} for ev in (db_events if db_events else INITIAL_EVENTS)}
    cluster_registry = {
        cl["cluster_type"]: {
            "category": cl["category"],
            "description": cl["description"],
            "persistence": cl.get("persistence", 0.6),
            "decay_rate": cl.get("decay_rate", 0.02)
        }
        for cl in (db_clusters if db_clusters else INITIAL_CLUSTERS)
    }
    
    # 3. Extract events
    processed_articles, extracted_events = run_gemini_batch_event_extraction(
        articles_metadata=scraped_articles_meta,
        api_key=api_key,
        registry=event_registry
    )
    
    # 4. Cluster signals
    generated_signals, updated_clusters = run_gemini_signals_clustering(
        events=extracted_events,
        api_key=api_key,
        cluster_registry=cluster_registry
    )
    
    # Enrich signals with article and event trace details for client traceability
    articles_map = {a["article_id"]: a for a in processed_articles}
    events_map = {e["event_id"]: e for e in extracted_events}
    
    for sig in generated_signals:
        evt = events_map.get(sig["event_id"], {})
        art = articles_map.get(sig["article_id"], {})
        sig["event_summary"] = evt.get("summary", "N/A")
        sig["article_title"] = art.get("title", "N/A")
        sig["article_url"] = art.get("url", "#")

    # Persist outputs to database
    try:
        from storage.db_client import add_article, add_event, add_signal
        for art in processed_articles:
            add_article(art)
        for ev in extracted_events:
            add_event(ev)
        for sig in generated_signals:
            add_signal(sig)
        print(f"[Pipeline] Successfully persisted {len(processed_articles)} articles, {len(extracted_events)} events, and {len(generated_signals)} signals to DB.")
    except Exception as e:
        print(f"[Pipeline Error] Failed to persist batch state to DB: {e}")

    duration = time.time() - start_time
    print("\n" + "=" * 50)
    print("IN-MEMORY BATCH PIPELINE RUN COMPLETE")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Articles Scraped:  {len(scraped_articles_meta)}")
    print(f"Articles Processed:{len(processed_articles)}")
    print(f"Events Extracted:  {len(extracted_events)}")
    print(f"Signals Generated: {len(generated_signals)}")
    print("=" * 50)
    
    # Format registry back as a list of dicts for client convenience
    registry_list = []
    for ev_type, info in event_registry.items():
        registry_list.append({
            "event_type": ev_type,
            "category": info.get("category", "general"),
            "description": info.get("description", "")
        })
        
    return {
        "articles": processed_articles,
        "events": extracted_events,
        "signals": generated_signals,
        "registry": registry_list
    }
