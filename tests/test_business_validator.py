from app.discovery.validation.business_validator import BusinessValidator
from app.models.candidate import CandidateBusiness
from app.schemas.discovery_request import DiscoveryRequest, Requirements, TargetBusiness


def _request():
    return DiscoveryRequest(
        target=TargetBusiness(
            industry="Dental clinics",
            services=["dental implants"],
            keywords=["dentist", "dental clinic"],
        ),
        locations=["Bangalore"],
        requirements=Requirements(),
    )


def test_directory_domain_detection_rejects_directory_candidate():
    candidate = CandidateBusiness(
        name="Practo Dental Listings",
        website="https://www.practo.com/bangalore/dentist",
        domain="practo.com",
        is_directory=True,
    )

    result = BusinessValidator().validate(candidate, _request())

    assert result.is_valid is False
    assert "directory" in result.rejection_reason


def test_directory_domain_is_rejected_even_with_business_like_name():
    candidate = CandidateBusiness(
        name="Alpha Dental Clinic",
        website="https://www.practo.com/bangalore/alpha-dental",
        domain="practo.com",
        is_directory=False,
    )

    result = BusinessValidator().validate(candidate, _request())

    assert result.is_valid is False
    assert "directory" in result.rejection_reason


def test_industry_relevance_uncertain_is_rejected():
    candidate = CandidateBusiness(
        name="Apex Wellness",
        website="https://apexwellness.example",
        domain="apexwellness.example",
        description="A local wellness provider.",
        locations=["Bangalore"],
    )

    result = BusinessValidator().validate(candidate, _request())

    assert result.is_valid is False
    assert "industry" in result.rejection_reason.lower()


def test_location_mismatch_is_rejected():
    candidate = CandidateBusiness(
        name="Apex Dental",
        website="https://apexdental.example",
        domain="apexdental.example",
        description="Dental clinic",
        locations=["Mysore"],
    )

    result = BusinessValidator().validate(candidate, _request())

    assert result.is_valid is False
    assert "location" in result.rejection_reason.lower()


def test_missing_location_is_rejected():
    candidate = CandidateBusiness(
        name="Apex Dental",
        website="https://apexdental.example",
        domain="apexdental.example",
    )

    result = BusinessValidator().validate(candidate, _request())

    assert result.is_valid is False
    assert "location" in result.rejection_reason.lower()


def test_contactless_business_is_rejected():
    candidate = CandidateBusiness(
        name="Apex Dental",
        industry="Dental clinics",
        locations=["Bangalore"],
    )

    result = BusinessValidator().validate(candidate, _request())

    assert result.is_valid is False
    assert "contact" in result.rejection_reason.lower()


def test_listing_title_is_rejected_as_not_a_business():
    candidate = CandidateBusiness(
        name="Top Restaurants in Bangalore",
        website="https://example.com",
        locations=["Bangalore"],
        industry="Restaurants",
    )

    result = BusinessValidator().validate(candidate, _request())

    assert result.is_valid is False
    assert "listing title" in result.rejection_reason.lower()


def test_candidate_without_name_website_or_intent_is_rejected():
    candidate = CandidateBusiness()

    result = BusinessValidator().validate(candidate, _request())

    assert result.is_valid is False
    assert "identifiable" in result.rejection_reason
