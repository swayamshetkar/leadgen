from typing import List, Dict, Optional


# ============================================================
# SERVICE KEYWORD FAMILIES
# Expand these freely without changing the core engine.
# ============================================================
SERVICE_KEYWORDS: Dict[str, List[str]] = {
    "seo": [
        "SEO", "search engine optimization", "SEO services", "SEO agency",
        "SEO company", "SEO consultant", "SEO expert", "local SEO", "technical SEO",
        "organic traffic", "Google ranking", "search rankings", "improve Google ranking",
        "search engine marketing", "on-page SEO", "off-page SEO", "link building",
        "keyword ranking", "SERP ranking", "Google visibility", "rank on Google",
    ],
    "social_media": [
        "social media", "social media management", "social media marketing",
        "social media manager", "Instagram marketing", "Instagram management",
        "Facebook marketing", "social media agency", "social media services",
        "content management", "social media strategy", "social media content",
        "Instagram growth", "Facebook page management", "social media presence",
        "community management", "social media consultant", "TikTok marketing",
    ],
    "branding": [
        "branding", "brand identity", "brand design", "rebranding", "brand strategy",
        "visual identity", "logo design", "brand guidelines", "branding agency",
        "brand designer", "creative agency", "brand development", "brand refresh",
        "corporate identity", "brand consulting", "brand positioning",
        "graphic design", "identity design",
    ],
    "website_design": [
        "website", "web design", "website design", "web development", "website development",
        "website redesign", "new website", "web designer", "web developer",
        "landing page", "website agency", "website builder", "responsive design",
        "mobile website", "ecommerce website", "website overhaul", "website revamp",
        "website makeover", "wordpress website",
    ],
    "content_creation": [
        "content creation", "content marketing", "content creator", "copywriting",
        "blog writing", "video content", "social media content", "content agency",
        "content strategy", "content writing", "article writing", "content producer",
        "storytelling", "content plan", "creative content",
    ],
    "digital_marketing": [
        "digital marketing", "digital marketing agency", "online marketing",
        "internet marketing", "performance marketing", "marketing agency",
        "growth marketing", "paid advertising", "Google ads", "Facebook ads",
        "PPC", "pay per click", "online advertising", "marketing consultant",
        "full-service marketing", "inbound marketing",
    ],
}

# Human-readable display names for each service key
SERVICE_DISPLAY_NAMES: Dict[str, str] = {
    "seo": "SEO",
    "social_media": "Social Media",
    "branding": "Branding",
    "website_design": "Website Design",
    "content_creation": "Content Creation",
    "digital_marketing": "Digital Marketing",
}

# ============================================================
# INTENT MODIFIER PHRASES
# Used for explicit intent query generation.
# ============================================================
INTENT_MODIFIERS: List[str] = [
    "looking for",
    "need",
    "needs",
    "seeking",
    "wanted",
    "hiring",
    "hire",
    "looking to hire",
    "looking for an agency",
    "looking for an expert",
    "looking for someone",
    "need help with",
    "need help",
    "require",
    "recommendation",
    "recommend",
    "anyone recommend",
    "can anyone suggest",
    "suggestions for",
    "searching for",
    "interested in",
    "want to improve",
    "trying to improve",
    "help needed",
    "any suggestions",
    "who should I hire",
]

# High-intent modifiers: produce 'high' confidence explicit-intent leads
HIGH_INTENT_MODIFIERS: List[str] = [
    "hiring", "hire", "looking to hire", "need", "looking for an agency",
    "looking for an expert", "need help with",
]

# ============================================================
# SERVICE NAME NORMALIZATION
# ============================================================
_ALIAS_MAP: Dict[str, str] = {
    # SEO
    "seo": "seo",
    "search engine optimization": "seo",
    "search engine": "seo",
    # Social Media
    "social media": "social_media",
    "social media management": "social_media",
    "instagram": "social_media",
    "facebook marketing": "social_media",
    "social": "social_media",
    "instagram marketing": "social_media",
    # Branding
    "branding": "branding",
    "brand": "branding",
    "brand identity": "branding",
    "logo": "branding",
    "logo design": "branding",
    "visual identity": "branding",
    "rebranding": "branding",
    "creative agency": "branding",
    # Website Design
    "website": "website_design",
    "web design": "website_design",
    "website design": "website_design",
    "web development": "website_design",
    "website development": "website_design",
    "website redesign": "website_design",
    "web designer": "website_design",
    "web developer": "website_design",
    "landing page": "website_design",
    # Content Creation
    "content": "content_creation",
    "content creation": "content_creation",
    "copywriting": "content_creation",
    "blog": "content_creation",
    "content marketing": "content_creation",
    "writing": "content_creation",
    # Digital Marketing
    "digital marketing": "digital_marketing",
    "online marketing": "digital_marketing",
    "paid ads": "digital_marketing",
    "ppc": "digital_marketing",
    "performance marketing": "digital_marketing",
    "google ads": "digital_marketing",
    "facebook ads": "digital_marketing",
    "marketing": "digital_marketing",
}


def normalize_service_name(raw: str) -> Optional[str]:
    """
    Map a user-supplied service name to a canonical key.
    E.g. 'SEO' -> 'seo', 'Social Media Management' -> 'social_media'
    Returns None if no match found.
    """
    raw_lower = raw.lower().strip()

    # Direct key match
    if raw_lower in SERVICE_KEYWORDS:
        return raw_lower

    # Alias map lookup
    if raw_lower in _ALIAS_MAP:
        return _ALIAS_MAP[raw_lower]

    # Partial / fuzzy matching
    for alias, canonical in _ALIAS_MAP.items():
        if alias in raw_lower or raw_lower in alias:
            return canonical

    return None


def get_keywords_for_service(service_key: str) -> List[str]:
    """Get all keyword variants for a normalized service key."""
    return SERVICE_KEYWORDS.get(service_key, [])


def get_primary_keywords_for_service(service_key: str, limit: int = 5) -> List[str]:
    """Get the top N most distinctive keywords for a service."""
    return SERVICE_KEYWORDS.get(service_key, [])[:limit]


def get_display_name(service_key: str) -> str:
    """Get human-readable display name for a service key."""
    return SERVICE_DISPLAY_NAMES.get(service_key, service_key.replace("_", " ").title())


def get_all_service_keys() -> List[str]:
    """Get all available canonical service keys."""
    return list(SERVICE_KEYWORDS.keys())
