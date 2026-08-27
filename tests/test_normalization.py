from app.discovery.normalization.domain import DomainNormalizer
from app.discovery.normalization.phone import PhoneNormalizer
from app.discovery.normalization.email import EmailNormalizer
from app.discovery.normalization.business import BusinessNormalizer


def test_domain_normalization():
    assert DomainNormalizer.normalize("https://www.example.com/contact?utm_source=google") == "example.com"
    assert DomainNormalizer.normalize("http://subdomain.clinic.co.uk/about/") == "clinic.co.uk"
    assert DomainNormalizer.normalize("http://localhost:8000") == "localhost"


def test_phone_normalization():
    # Indian standard mobile
    norm_in = PhoneNormalizer.normalize_e164("9876543210", default_region="IN")
    assert norm_in == "+919876543210"

    # US number
    norm_us = PhoneNormalizer.normalize_e164("(202) 555-0123", default_region="US")
    assert norm_us == "+12025550123"

    # Digits key extraction (for matching)
    key1 = PhoneNormalizer.digits_key("+91 98765 43210")
    key2 = PhoneNormalizer.digits_key("09876543210")
    assert key1 == key2 == "9876543210"


def test_email_normalization():
    assert EmailNormalizer.normalize("  INFO@Example.COM ") == "info@example.com"
    assert EmailNormalizer.normalize("invalid-email") is None


def test_business_name_normalization():
    norm = BusinessNormalizer.normalize_name("ABC Dental Clinic Pvt. Ltd.")
    assert "Pvt" not in norm
    assert "Ltd" not in norm
    assert "ABC Dental Clinic" in norm

    match_key = BusinessNormalizer.match_key("ABC Dental Clinic Pvt Ltd")
    assert match_key == "abcdental"
