from app.discovery.extractors.jsonld import JSONLDExtractor


def test_jsonld_local_business_extraction():
    html_doc = """
    <!DOCTYPE html>
    <html>
    <head>
        <script type="application/ld+json">
        {
            "@context": "https://schema.org",
            "@type": "Dentist",
            "name": "Apex Dental Clinic",
            "image": "https://example.com/logo.jpg",
            "telephone": "+91 80 1234 5678",
            "email": "contact@apexdental.com",
            "address": {
                "@type": "PostalAddress",
                "streetAddress": "123 Indiranagar 100ft Road",
                "addressLocality": "Bangalore",
                "addressRegion": "Karnataka",
                "postalCode": "560038",
                "addressCountry": "IN"
            },
            "url": "https://apexdental.com",
            "sameAs": [
                "https://www.facebook.com/apexdentalblr",
                "https://www.instagram.com/apexdentalblr"
            ],
            "description": "Premier cosmetic dentistry and dental implants in Bangalore."
        }
        </script>
    </head>
    <body>
        <h1>Apex Dental Clinic</h1>
    </body>
    </html>
    """

    extractor = JSONLDExtractor()
    results = extractor.extract(html_doc, "https://apexdental.com")

    assert len(results) == 1
    biz = results[0]
    assert biz["name"] == "Apex Dental Clinic"
    assert biz["telephone"] == "+91 80 1234 5678"
    assert biz["email"] == "contact@apexdental.com"
    assert "Indiranagar" in biz["address"]
    assert "Bangalore" in biz["address"]
    assert len(biz["sameAs"]) == 2
    assert "https://www.instagram.com/apexdentalblr" in biz["sameAs"]


def test_jsonld_graph_extraction():
    html_graph = """
    <script type="application/ld+json">
    {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "WebSite",
                "url": "https://smilecare.com",
                "name": "Smile Care"
            },
            {
                "@type": "MedicalClinic",
                "name": "Smile Care Dental Health",
                "telephone": "080-98765432",
                "email": "info@smilecare.com",
                "url": "https://smilecare.com",
                "description": "Comprehensive dental care for the entire family."
            }
        ]
    }
    </script>
    """
    extractor = JSONLDExtractor()
    results = extractor.extract(html_graph, "https://smilecare.com")

    assert len(results) == 1
    assert results[0]["name"] == "Smile Care Dental Health"
    assert results[0]["email"] == "info@smilecare.com"
