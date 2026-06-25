import requests
import bs4
import time
import os
import json
from datetime import datetime

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def parse_article_date(date_str):
    """
    Parses Moneycontrol article dates from tag pages (e.g. 'June 17, 2026 11:59 AM IST')
    or company article pages (e.g. '3.47 pm | 19 Jun 2026') into a datetime object.
    """
    clean_date = date_str.replace(' IST', '').strip()
    
    # Try company article page format: e.g. "3.47 pm | 19 Jun 2026"
    if '|' in clean_date:
        try:
            parts = clean_date.split('|')
            time_part = parts[0].strip().replace('am', 'AM').replace('pm', 'PM')
            date_part = parts[1].strip()
            combined = f"{date_part} {time_part}"
            # E.g. "19 Jun 2026 3.47 PM"
            for fmt in ('%d %b %Y %I.%M %p', '%d %B %Y %I.%M %p', '%d %b %Y %H.%M', '%d %B %Y %H.%M'):
                try:
                    return datetime.strptime(combined, fmt)
                except ValueError:
                    continue
        except Exception:
            pass
            
    # Try tag page format: e.g. "June 17, 2026 11:59 AM"
    for fmt in ('%B %d, %Y %I:%M %p', '%b %d, %Y %I:%M %p', '%B %d, %Y %H:%M', '%b %d, %Y %H:%M'):
        try:
            return datetime.strptime(clean_date, fmt)
        except ValueError:
            continue
            
    return None

def scrape_company_article_page(url, cutoff_dt=None):
    """
    Scrapes company article pages from Moneycontrol (e.g. /company-article/)
    which lists company-specific news.
    """
    print(f"[Scraper] Scraping company article page: {url}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        # Note: Moneycontrol company-article pages often return HTTP 410 (Gone) 
        # but serve the complete body anyway. We check body length instead of status code.
        if response.status_code not in (200, 410):
            print(f"[Scraper Error] HTTP status {response.status_code} received.")
            return []
    except Exception as e:
        print(f"[Scraper Error] Connection failed: {str(e)}")
        return []

    soup = bs4.BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all('div', class_='MT15')
    articles = []

    print(f"[Scraper] Found {len(rows)} potential article elements on company page.")

    for row in rows:
        a_tags = row.find_all('a')
        link_tag = None
        title = ""
        link = ""
        
        for a in a_tags:
            t = a.get_text().strip()
            h = a.get('href', '').strip()
            if t and h:
                title = t
                link = h
                link_tag = a
                break
                
        if not link:
            continue

        if link.startswith('/'):
            link = f"https://www.moneycontrol.com{link}"

        # Extract text components to find date & description
        all_text = [t.strip() for t in row.get_text("\n").split("\n") if t.strip()]
        date_str = "N/A"
        desc_str = "N/A"
        
        # Sift through lines to find date and description
        for line in all_text:
            if '|' in line:
                date_str = line
            elif line != title and date_str != line:
                desc_str = line

        # Parse date and enforce cutoff check
        dt = parse_article_date(date_str) if date_str != "N/A" else None
        
        if cutoff_dt and dt:
            if dt < cutoff_dt:
                print(f"[Scraper] Reached article dated {date_str} (older than cutoff). Stopping.")
                break

        articles.append({
            "title": title,
            "link": link,
            "date": date_str,
            "description": desc_str
        })

    return articles

def scrape_tag_feed_page(url, cutoff_dt=None, max_pages=5):
    """
    Scrapes standard Moneycontrol tag feeds (e.g. /tags/tcs.html/) which are paginated.
    Fetches all pages in parallel to maximize performance, then processes them sequentially to enforce cutoff boundaries.
    """
    print(f"[Scraper] Scraping tag feed: {url}")
    import concurrent.futures
    
    pages_data = {}
    
    def fetch_page(p_num):
        page_url = url if p_num == 1 else f"{url.rstrip('/')}/page-{p_num}/"
        print(f"[Scraper] Crawling Tag Feed Page {p_num}: {page_url}...")
        try:
            response = requests.get(page_url, headers=HEADERS, timeout=15)
            if response.status_code == 200:
                return p_num, response.text
            else:
                print(f"[Scraper] Page {p_num} returned HTTP {response.status_code}")
        except Exception as e:
            print(f"[Scraper] Connection error on page {p_num}: {str(e)}")
        return p_num, None

    # Fetch pages concurrently (max 5 pages defaults)
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_pages) as executor:
        futures = [executor.submit(fetch_page, p) for p in range(1, max_pages + 1)]
        for future in concurrent.futures.as_completed(futures):
            p_num, html = future.result()
            if html:
                pages_data[p_num] = html

    articles = []
    stop_scraping = False

    # Process pages in order
    for page_num in sorted(pages_data.keys()):
        if stop_scraping:
            break
            
        html = pages_data[page_num]
        soup = bs4.BeautifulSoup(html, "html.parser")
        items = [li for li in soup.find_all('li') if li.get('id') and li.get('id').startswith('newslist-')]

        if not items:
            continue

        for item in items:
            a_elem = item.find('a')
            if not a_elem:
                continue

            link = a_elem.get('href', '').strip()
            title = a_elem.get('title', '').strip()
            if not title:
                h2_elem = a_elem.find('h2')
                title = h2_elem.get_text().strip() if h2_elem else "N/A"

            date_str = "N/A"
            comment = item.find(string=lambda text: isinstance(text, bs4.Comment))
            if comment and 'span' in comment:
                comment_soup = bs4.BeautifulSoup(comment, 'html.parser')
                date_str = comment_soup.get_text().strip()
            else:
                span_elem = item.find('span')
                if span_elem:
                    date_str = span_elem.get_text().strip()

            p_elem = item.find('p')
            desc_str = p_elem.get_text().strip() if p_elem else "N/A"

            dt = parse_article_date(date_str) if date_str != "N/A" else None
            
            if cutoff_dt and dt:
                if dt < cutoff_dt:
                    print(f"[Scraper] Reached article dated {date_str} (older than cutoff). Stopping.")
                    stop_scraping = True
                    break

            if link.startswith('/'):
                link = f"https://www.moneycontrol.com{link}"

            articles.append({
                "title": title,
                "link": link,
                "date": date_str,
                "description": desc_str
            })

    return articles

def scrape_articles_until_date(url, cutoff_dt=None, output_file=None, max_pages=5):
    """
    Unified entrypoint to scrape Moneycontrol company article lists or tag feeds.
    """
    url = url.strip()
    if "/company-article/" in url:
        scraped_articles = scrape_company_article_page(url, cutoff_dt)
    else:
        scraped_articles = scrape_tag_feed_page(url, cutoff_dt, max_pages)

    if output_file and scraped_articles:
        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(scraped_articles, f, indent=4, ensure_ascii=False)
        print(f"[Scraper] Saved {len(scraped_articles)} articles to '{output_file}'")

    return scraped_articles
