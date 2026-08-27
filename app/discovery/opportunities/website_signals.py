from typing import List, Tuple
from bs4 import BeautifulSoup


class WebsiteSignalDetector:
    """
    Analyzes crawled HTML for website quality/design signals.
    Detects potential Website Design / Web Development opportunities.
    """

    def detect(self, html: str, url: str = "") -> Tuple[List[str], List[str]]:
        """
        Returns (signals, evidence_urls) tuple.
        signals: list of observable signal descriptions
        evidence_urls: list of source URLs confirming signals
        """
        evidence = [url] if url else []

        if not html:
            return ["No website content accessible"], evidence

        signals = []

        try:
            soup = BeautifulSoup(html, "lxml")

            # 1. Mobile viewport meta tag
            viewport = soup.find("meta", attrs={"name": "viewport"})
            if not viewport:
                signals.append("Missing viewport meta tag — website likely not mobile-optimized")

            # 2. Page content thickness
            body = soup.find("body")
            body_text = body.get_text(separator=" ", strip=True) if body else ""
            if len(body_text) < 300:
                signals.append("Very thin page content (under 300 characters) — weak online presence")
            elif len(body_text) < 700:
                signals.append("Limited page content — room to expand service descriptions")

            # 3. Heading structure
            h1 = soup.find("h1")
            if not h1:
                signals.append("No H1 heading found — weak content structure")

            # 4. Navigation
            nav = soup.find("nav") or soup.find(attrs={"role": "navigation"})
            if not nav:
                nav_links = soup.select("ul li a")
                if len(nav_links) < 3:
                    signals.append("No clear navigation structure — poor information architecture")

            # 5. Call to action
            cta_keywords = ["contact", "book", "appointment", "call", "get started",
                            "enquire", "consult", "schedule", "request"]
            buttons = soup.find_all(["button", "a"])
            button_texts = [b.get_text(strip=True).lower() for b in buttons]
            has_cta = any(any(kw in t for kw in cta_keywords) for t in button_texts if t)
            if not has_cta:
                signals.append("No clear call-to-action (CTA) buttons found — weak conversion flow")

            # 6. Contact information visible
            page_text_lower = body_text.lower()
            has_phone_hint = (
                any(char.isdigit() for char in body_text) and
                any(kw in page_text_lower for kw in ["+", "tel", "phone", "call us", "contact"])
            )
            has_email_hint = "@" in body_text or "email" in page_text_lower
            if not has_phone_hint and not has_email_hint:
                signals.append("No visible contact information on page — makes it hard for customers to reach out")

            # 7. Service description section
            service_section_kw = ["service", "treatment", "what we do", "our work",
                                   "solutions", "offerings", "specializ", "expertise"]
            has_services = any(kw in page_text_lower for kw in service_section_kw)
            if not has_services:
                signals.append("No service description section detected — missed opportunity to convert visitors")

            # 8. Outdated HTML (tables for layout, no semantic tags)
            semantic_tags = soup.find_all(["article", "section", "aside", "header", "footer", "main"])
            layout_tables = soup.find_all("table")
            if len(layout_tables) > 3 and len(semantic_tags) == 0:
                signals.append("Outdated table-based HTML layout — website may appear dated")

        except Exception:
            pass

        return signals, evidence
