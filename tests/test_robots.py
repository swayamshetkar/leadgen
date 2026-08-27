import pytest
from app.discovery.website.robots import RobotsInspector


def test_robots_parser_directives():
    robots_text = """
    User-agent: *
    Disallow: /admin/
    Disallow: /private/
    Allow: /public/
    
    Sitemap: https://example.com/sitemap.xml
    Sitemap: https://example.com/sitemap_index.xml
    """

    inspector = RobotsInspector()
    lines = robots_text.splitlines()
    
    import urllib.robotparser
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(lines)

    sitemaps = []
    for line in lines:
        if line.strip().lower().startswith("sitemap:"):
            sitemaps.append(line.split(":", 1)[1].strip())

    assert len(sitemaps) == 2
    assert "https://example.com/sitemap.xml" in sitemaps

    assert inspector.can_fetch(rp, "https://example.com/about") is True
    assert inspector.can_fetch(rp, "https://example.com/contact") is True
    assert inspector.can_fetch(rp, "https://example.com/admin/settings") is False
