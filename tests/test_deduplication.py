from app.models.candidate import CandidateBusiness, EmailRecord, PhoneRecord
from app.schemas.discovery_request import Requirements
from app.discovery.deduplication.matcher import CandidateMatcher
from app.discovery.deduplication.merger import CandidateMerger


def test_matcher_multi_tier():
    matcher = CandidateMatcher()

    # Tier 1: Domain match
    c1 = CandidateBusiness(name="Smile Dental", website="https://smiledental.com", domain="smiledental.com")
    c2 = CandidateBusiness(name="Smile Dental Clinic Bangalore", website="https://www.smiledental.com/contact", domain="smiledental.com")
    assert matcher.is_match(c1, c2) is True

    # Tier 2: Phone match
    c3 = CandidateBusiness(name="ABC Teeth", phone_numbers=[PhoneRecord(value="+919876543210")])
    c4 = CandidateBusiness(name="Dr. ABC Clinic", phone_numbers=[PhoneRecord(value="098765 43210")])
    assert matcher.is_match(c3, c4) is True

    # Tier 3: Social handle match
    c5 = CandidateBusiness(name="Dentist Bangalore", social_profiles={"instagram": "https://instagram.com/blissdental"})
    c6 = CandidateBusiness(name="Bliss Dental Care", social_profiles={"instagram": "https://www.instagram.com/blissdental/"})
    assert matcher.is_match(c5, c6) is True

    # Tier 4: Business name + Location match
    c7 = CandidateBusiness(name="Apex Dental Clinic", locations=["Bangalore"])
    c8 = CandidateBusiness(name="Apex Dental Care", locations=["Bangalore"])
    assert matcher.is_match(c7, c8) is True


def test_merger_aggregates_sources_and_evidence():
    merger = CandidateMerger()

    c1 = CandidateBusiness(
        name="Apex Dental",
        website="https://apexdental.com",
        domain="apexdental.com",
        sources=["search"],
        locations=["Bangalore"]
    )
    c1.add_evidence("website", "https://apexdental.com", "search", confidence=0.8)

    c2 = CandidateBusiness(
        name="Apex Dental Clinic",
        website="https://apexdental.com",
        domain="apexdental.com",
        phone_numbers=[PhoneRecord(value="+918012345678")],
        sources=["maps"],
        locations=["Bangalore"]
    )
    c2.add_evidence("phone", "+918012345678", "maps", confidence=0.9)

    merged_leads = merger.merge_candidates([c1, c2])
    assert len(merged_leads) == 1
    lead = merged_leads[0]

    assert "Apex Dental" in lead.name
    assert len(lead.sources) == 2
    assert "search" in lead.sources
    assert "maps" in lead.sources
    assert len(lead.evidence) == 2
    assert len(lead.phone_numbers) == 1


def test_contactability_allows_partial_contact():
    """
    CRITICAL RULE:
    Discovery must accept businesses based on relevance, NOT on whether every optional field is present.
    Missing email, missing phone, or missing LinkedIn must NEVER cause a candidate to be rejected
    unless explicitly specified in requirements.must_have.
    """
    merger = CandidateMerger()

    # Lead A: Name + Website + Phone, but NO email, NO LinkedIn
    lead_a = CandidateBusiness(
        name="ABC Dental",
        website="https://abcdental.com",
        domain="abcdental.com",
        phone_numbers=[PhoneRecord(value="+919999999999")],
        emails=[],
        social_profiles={"instagram": None, "linkedin": None},
        industry="Dental clinics",
        locations=["Bangalore"],
    )

    # Lead B: Name + Phone only, NO website, NO email
    lead_b = CandidateBusiness(
        name="XYZ Dental",
        phone_numbers=[PhoneRecord(value="+918888888888")],
        website=None,
        emails=[],
        industry="Dental clinics",
        locations=["Bangalore"],
    )

    # Lead C: Name + Website only, NO phone, NO email
    lead_c = CandidateBusiness(
        name="Dental Care Center",
        website="https://dentalcare.com",
        domain="dentalcare.com",
        phone_numbers=[],
        emails=[],
        industry="Dental clinics",
        locations=["Bangalore"],
    )

    # A website, phone, or email is sufficient; all three have a usable path.
    results_no_constraint = merger.merge_candidates([lead_a, lead_b, lead_c], requirements=Requirements())
    assert len(results_no_constraint) == 3

    # With must_have: ["website"] -> Lead A and Lead C are kept, Lead B is excluded
    results_with_must_have = merger.merge_candidates(
        [lead_a, lead_b, lead_c],
        requirements=Requirements(must_have=["website"])
    )
    assert len(results_with_must_have) == 2
    names = [l.name for l in results_with_must_have]
    assert "ABC Dental" in names
    assert "Dental Care Center" in names
    assert "XYZ Dental" not in names


def test_merger_does_not_mix_contacts_across_different_domains():
    matcher = CandidateMatcher()
    merger = CandidateMerger()

    c1 = CandidateBusiness(
        name="Apex Dental",
        website="https://apexdental.com",
        domain="apexdental.com",
        phone_numbers=[PhoneRecord(value="+918012345678")],
        emails=[EmailRecord(value="hello@apexdental.com")],
        locations=["Bangalore"],
    )
    c2 = CandidateBusiness(
        name="Apex Dental",
        website="https://apexsmiles.com",
        domain="apexsmiles.com",
        phone_numbers=[PhoneRecord(value="+918012345678")],
        emails=[EmailRecord(value="hello@apexsmiles.com")],
        locations=["Bangalore"],
    )

    assert matcher.is_match(c1, c2) is False

    merged_leads = merger.merge_candidates([c1, c2])

    assert len(merged_leads) == 2
    by_domain = {lead.domain: lead for lead in merged_leads}
    assert [email.value for email in by_domain["apexdental.com"].emails] == ["hello@apexdental.com"]
    assert [email.value for email in by_domain["apexsmiles.com"].emails] == ["hello@apexsmiles.com"]
