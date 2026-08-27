from app.schemas.discovery_request import DiscoveryRequest, TargetBusiness, Requirements
from app.discovery.query_generator import QueryGenerator


def test_query_generator_multiple_locations():
    request = DiscoveryRequest(
        target=TargetBusiness(
            industry="Dental clinics",
            services=["dental implants", "cosmetic dentistry"],
            keywords=["dentist", "dental clinic"]
        ),
        locations=["Bangalore", "Mysore", "Hyderabad"],
        lead_objective="Find businesses that may need a new website",
        requirements=Requirements(
            must_have=["website"],
            preferred=["instagram", "email"],
            exclude=["hospitals"]
        )
    )

    gen = QueryGenerator()
    queries = gen.generate_queries(request)

    assert len(queries) > 20

    families = {q.family for q in queries}
    assert "basic" in families
    assert "service" in families
    assert "contact" in families
    assert "intent" in families
    assert "dork" in families
    assert "social_dork" in families
    assert all(q.query_type == "business_discovery" for q in queries)
    assert all(q.service is None for q in queries)

    locations = {q.location for q in queries}
    assert "Bangalore" in locations
    assert "Mysore" in locations
    assert "Hyderabad" in locations

    # Verify specific dork query presence
    dork_texts = [q.query for q in queries if q.family == "dork"]
    assert any("inurl:contact" in d for d in dork_texts)
    assert any('"Bangalore"' in d for d in dork_texts)

    # Verify social dorks
    social_texts = [q.query for q in queries if q.family == "social_dork"]
    assert any("site:instagram.com" in s for s in social_texts)
    assert any("site:linkedin.com" in s for s in social_texts)
