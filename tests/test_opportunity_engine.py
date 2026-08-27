from app.discovery.opportunities.engine import OpportunityEngine


def test_website_design_opportunity_medium_with_two_signals():
    html = """
    <html>
      <head><meta name="viewport" content="width=device-width, initial-scale=1"></head>
      <body>
        <nav><a href="/">Home</a><a href="/services">Services</a><a href="/contact">Contact</a></nav>
        <p>Services contact call 9876543210.</p>
        <a href="/book">Book appointment</a>
      </body>
    </html>
    """

    result = OpportunityEngine().evaluate(
        services_offered=["Website Design"],
        html=html,
        page_url="https://clinic.example",
    )

    assert result.has_opportunities is True
    assert result.opportunities[0].service == "website_design"
    assert result.opportunities[0].confidence == "medium"
    assert len(result.opportunities[0].signals) == 2


def test_seo_opportunity_high_with_three_or_more_signals():
    html = "<html><body><p>Short dental page.</p></body></html>"

    result = OpportunityEngine().evaluate(
        services_offered=["SEO"],
        html=html,
        meta={},
        jsonld_items=[],
        location_keywords=["Bangalore"],
        page_url="https://clinic.example",
    )

    assert result.has_opportunities is True
    assert result.opportunities[0].service == "seo"
    assert result.opportunities[0].confidence == "high"
    assert len(result.opportunities[0].signals) >= 3


def test_single_weak_signal_does_not_create_opportunity():
    result = OpportunityEngine().evaluate(
        services_offered=["Social Media"],
        social_profiles={},
        business_name="Apex Dental",
        domain="apexdental.com",
    )

    assert result.has_opportunities is False
    assert result.opportunities == []
