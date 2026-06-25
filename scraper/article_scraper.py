import requests
import bs4
import urllib3

# Suppress insecure request warnings if they happen
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Define headers to mimic browser request
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
}

def fetch_article_text(url, timeout_secs=10, session=None):
    """
    Downloads and extracts the clean, full text of a Moneycontrol article from its URL.
    Returns the extracted text. Raises Exception on failure or if text is missing.
    """
    try:
        if session is not None:
            response = session.get(url, headers=HEADERS, timeout=timeout_secs, verify=False)
        else:
            response = requests.get(url, headers=HEADERS, timeout=timeout_secs, verify=False)
    except Exception as e:
        raise Exception(f"Connection failure to URL {url}: {str(e)}")

    if response.status_code != 200:
        raise Exception(f"Failed to fetch page. HTTP status code: {response.status_code}")

    soup = bs4.BeautifulSoup(response.text, "html.parser")
    
    # Target Moneycontrol's main article container: div.page_left_wrapper -> div.content_wrapper
    wrapper = soup.find('div', class_='page_left_wrapper')
    content_div = None
    if wrapper:
        content_div = wrapper.find(class_='content_wrapper')
        
    # Fallback to direct content_wrapper search if page_left_wrapper is not present
    if not content_div:
        content_div = soup.find(class_='content_wrapper') or soup.find(class_='content_page')

    if not content_div:
        # If no article wrapper is found, see if we can find any paragraphs on the page
        # but filter out obvious layout garbage. Moneycontrol has page content inside wrapper.
        raise Exception("Article content wrapper (content_wrapper) not found on page.")

    # Extract all paragraph texts
    paragraphs = content_div.find_all('p')
    clean_paras = [p.get_text().strip() for p in paragraphs if p.get_text().strip()]
    
    full_text = "\n".join(clean_paras)
    
    # Perform strict size checks to identify premium/PRO lockouts or blank redirects
    if not full_text or len(full_text) < 150:
        raise Exception(f"Extracted article text is too short or missing ({len(full_text) if full_text else 0} chars).")
        
    return full_text
