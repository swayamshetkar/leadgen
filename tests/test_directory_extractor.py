from app.discovery.extractors.directory import DirectoryExtractor


def test_directory_extractor_extracts_separate_business_cards():
    html = """
    <html><body>
      <div class="business-card">
        <h2>Alpha Dental Clinic</h2>
        <span class="address">Indiranagar, Bangalore</span>
        <span>+91 9876543210</span>
        <span>alpha@example.com</span>
      </div>
      <div class="business-card">
        <h2>Beta Smile Care</h2>
        <span class="address">Koramangala, Bangalore</span>
        <span>+91 9876543211</span>
        <span>beta@example.com</span>
      </div>
      <div class="business-card">
        <h2>Gamma Tooth Studio</h2>
        <span class="address">Whitefield, Bangalore</span>
        <span>+91 9876543212</span>
        <span>gamma@example.com</span>
      </div>
    </body></html>
    """

    candidates = DirectoryExtractor().extract_businesses(
        html,
        source_url="https://www.practo.com/bangalore/dentist",
        target_industry="Dental clinics",
        target_location="Bangalore",
    )

    assert len(candidates) == 3
    assert [c.name for c in candidates] == [
        "Alpha Dental Clinic",
        "Beta Smile Care",
        "Gamma Tooth Studio",
    ]


def test_directory_extractor_does_not_cross_contaminate_contacts():
    html = """
    <html><body>
      <article>
        <h3>Alpha Dental Clinic</h3>
        <p>+91 9876543210 alpha@example.com</p>
      </article>
      <article>
        <h3>Beta Smile Care</h3>
        <p>+91 9876543211 beta@example.com</p>
      </article>
      <article>
        <h3>Gamma Tooth Studio</h3>
        <p>+91 9876543212 gamma@example.com</p>
      </article>
    </body></html>
    """

    candidates = DirectoryExtractor().extract_businesses(
        html,
        source_url="https://www.practo.com/bangalore/dentist",
        target_industry="Dental clinics",
        target_location="Bangalore",
    )

    by_name = {c.name: c for c in candidates}

    assert by_name["Alpha Dental Clinic"].emails[0].value == "alpha@example.com"
    assert by_name["Beta Smile Care"].emails[0].value == "beta@example.com"
    assert by_name["Gamma Tooth Studio"].phone_numbers[0].value.endswith("9876543212")
    assert all(len(c.emails) == 1 for c in candidates)
    assert all(len(c.phone_numbers) == 1 for c in candidates)
