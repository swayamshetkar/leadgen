from app.discovery.opportunities.service_profiles import (
    INTENT_MODIFIERS,
    get_keywords_for_service,
    normalize_service_name,
)


def test_keyword_expansion_per_service():
    seo_keywords = get_keywords_for_service("seo")
    social_keywords = get_keywords_for_service("social_media")

    assert "search engine optimization" in seo_keywords
    assert "local SEO" in seo_keywords
    assert "social media management" in social_keywords
    assert "Instagram marketing" in social_keywords


def test_intent_modifiers_include_sales_intent_phrases():
    modifiers = {m.lower() for m in INTENT_MODIFIERS}

    assert "looking for" in modifiers
    assert "hiring" in modifiers
    assert "recommend" in modifiers
    assert "want to improve" in modifiers


def test_normalize_service_name_aliases():
    assert normalize_service_name("SEO") == "seo"
    assert normalize_service_name("Social Media Management") == "social_media"
    assert normalize_service_name("Logo Design") == "branding"
    assert normalize_service_name("Website Redesign") == "website_design"
