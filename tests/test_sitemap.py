from app.discovery.website.sitemap import SitemapParser


def test_sitemap_xml_parsing_and_priority_scoring():
    xml_content = b"""<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url>
            <loc>https://exampleclinic.com/about-us</loc>
            <priority>0.8</priority>
        </url>
        <url>
            <loc>https://exampleclinic.com/contact</loc>
            <priority>0.9</priority>
        </url>
        <url>
            <loc>https://exampleclinic.com/dental-implants-service</loc>
            <priority>0.7</priority>
        </url>
        <url>
            <loc>https://exampleclinic.com/blog/how-to-brush-teeth-2024</loc>
            <priority>0.3</priority>
        </url>
    </urlset>
    """

    parser = SitemapParser()
    urls = parser._parse_xml_content(xml_content)

    assert len(urls) == 4
    assert "https://exampleclinic.com/contact" in urls

    scored_urls = parser._score_and_filter_urls(urls, max_urls=5)
    # Contact, about, and service pages should rank higher than blog
    assert len(scored_urls) >= 3
    assert scored_urls[0] in ("https://exampleclinic.com/contact", "https://exampleclinic.com/about-us", "https://exampleclinic.com/dental-implants-service")
