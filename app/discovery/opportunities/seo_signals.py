from typing import List, Tuple, Dict, Any, Optional
from bs4 import BeautifulSoup


class SEOSignalDetector:
    """
    Analyzes page HTML and metadata for SEO quality signals.
    Detects potential SEO service opportunities.
    """

    def detect(
        self,
        html: str,
        meta: Dict[str, Any],
        jsonld_items: List[Dict[str, Any]],
        location_keywords: Optional[List[str]] = None,
        url: str = "",
    ) -> Tuple[List[str], List[str]]:
        """
        Returns (signals, evidence_urls) tuple.
        """
        signals = []
        evidence = [url] if url else []

        if not html and not meta:
            return ["No page content available for SEO analysis"], evidence

        # 1. Page title analysis
        title = (meta.get("title") or "").strip()
        if not title:
            signals.append("Missing page title tag — critical SEO issue")
        elif len(title) < 10:
            signals.append(f"Very short page title: '{title}' — likely not optimized")
        elif len(title) > 70:
            signals.append(f"Page title too long ({len(title)} chars) — truncated in search results")

        # 2. Meta description
        description = (meta.get("description") or "").strip()
        if not description:
            signals.append("Missing meta description — reduces click-through rates from search")
        elif len(description) < 50:
            signals.append(f"Very short meta description ({len(description)} chars) — missed SEO opportunity")

        # 3. Structured data / schema.org
        has_schema = bool(jsonld_items)
        if not has_schema and html:
            try:
                soup = BeautifulSoup(html, "lxml")
                schema_scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
                microdata = soup.find_all(attrs={"itemscope": True})
                has_schema = bool(schema_scripts or microdata)
            except Exception:
                pass
        if not has_schema:
            signals.append("No structured data (schema.org/JSON-LD) — missing local SEO and rich results opportunity")

        # 4. Location keyword targeting
        if location_keywords and html:
            page_lower = html.lower()
            found_location = any(loc.lower() in page_lower for loc in location_keywords if loc)
            if not found_location:
                signals.append("Location keywords not found on page — weak local SEO targeting")

        # 5. HTML heading and content analysis
        if html:
            try:
                soup = BeautifulSoup(html, "lxml")

                h1_tags = soup.find_all("h1")
                if not h1_tags:
                    signals.append("No H1 tag — important keyword targeting element missing")
                elif len(h1_tags) > 3:
                    signals.append(f"Multiple H1 tags ({len(h1_tags)}) — dilutes SEO keyword focus")

                body = soup.find("body")
                body_text = body.get_text(strip=True) if body else ""
                word_count = len(body_text.split())
                if word_count < 150:
                    signals.append(f"Very thin content ({word_count} words) — poor for organic rankings")

                # 6. Internal linking
                all_links = soup.find_all("a", href=True)
                internal_links = [
                    a for a in all_links
                    if a["href"].startswith("/") or a["href"].startswith("#")
                ]
                if len(internal_links) < 3:
                    signals.append("Very few internal links — weak site architecture for SEO")

            except Exception:
                pass

        return signals, evidence
