import urllib.parse
from typing import Optional
import tldextract


def normalize_url(url: str) -> str:
    """
    Ensures a scheme is present, strips URL fragments and trailing slashes.
    """
    if not url:
        return ""
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    
    parsed = urllib.parse.urlparse(url)
    # Strip tracking query parameters commonly found in search engines
    query_params = urllib.parse.parse_qsl(parsed.query)
    filtered_query = [
        (k, v) for k, v in query_params
        if not k.startswith("utm_") and k not in ("fbclid", "gclid", "ref", "source")
    ]
    new_query = urllib.parse.urlencode(filtered_query)
    
    path = parsed.path
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
        
    normalized = urllib.parse.urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        parsed.params,
        new_query,
        ""  # strip fragment
    ))
    return normalized


def extract_domain(url: str) -> str:
    """
    Extracts the root registered domain (e.g., example.com from www.sub.example.com/page).
    """
    if not url:
        return ""
    extracted = tldextract.extract(url)
    if extracted.domain and extracted.suffix:
        return f"{extracted.domain}.{extracted.suffix}".lower()
    # Fallback to netloc without port
    parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
    netloc = parsed.netloc.split(":")[0].lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def extract_hostname(url: str) -> str:
    """
    Extracts full hostname (e.g., clinic.example.com).
    """
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
    return parsed.netloc.split(":")[0].lower()


def is_same_domain(url1: str, url2: str) -> bool:
    d1 = extract_domain(url1)
    d2 = extract_domain(url2)
    return bool(d1 and d2 and d1 == d2)


def is_valid_http_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(url)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False
