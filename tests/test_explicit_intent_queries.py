from app.discovery.query_generator import QueryGenerator


def test_explicit_intent_queries_are_tagged():
    gen = QueryGenerator()

    queries = gen.generate_explicit_intent_queries(
        services_offered=["SEO"],
        locations=["Bangalore"],
        target_industry="Dental clinics",
    )

    assert queries
    service_queries = [q for q in queries if q.query_type == "explicit_intent"]
    assert service_queries
    assert all(q.family == "explicit_intent" for q in service_queries)
    assert all(q.service == "seo" for q in service_queries)
    assert all(q.intent_type for q in service_queries)
    assert any("looking" in q.query.lower() or "need" in q.query.lower() for q in service_queries)


def test_explicit_intent_queries_are_capped_per_service_location():
    gen = QueryGenerator()

    queries = gen.generate_explicit_intent_queries(
        services_offered=["SEO"],
        locations=["Bangalore"],
        target_industry="",
    )

    assert len([q for q in queries if q.service == "seo"]) <= 8
