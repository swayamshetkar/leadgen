from typing import List, Tuple
from bs4 import BeautifulSoup


class ContentSignalDetector:
    """
    Detects content quality and depth signals on a website.
    Detects potential Content Creation / Marketing opportunities.
    """

    def detect(self, html: str, url: str = "") -> Tuple[List[str], List[str]]:
        """
        Returns (signals, evidence_urls) tuple.
        """
        evidence = [url] if url else []

        if not html:
            return ["No content accessible for analysis"], evidence

        signals = []

        try:
            soup = BeautifulSoup(html, "lxml")

            body = soup.find("body")
            body_text = body.get_text(separator=" ", strip=True) if body else ""
            word_count = len(body_text.split())

            # 1. Thin overall content
            if word_count < 200:
                signals.append(
                    f"Very thin page content ({word_count} words) — insufficient for meaningful engagement"
                )
            elif word_count < 400:
                signals.append(f"Limited page content ({word_count} words) — room for richer content strategy")

            # 2. No blog/articles/news section
            blog_indicators = ["blog", "article", "news", "insights", "resources", "tips", "guide", "post"]
            links = [a.get("href", "").lower() for a in soup.find_all("a", href=True)]
            page_text_lower = body_text.lower()
            has_blog = (
                any(ind in page_text_lower for ind in blog_indicators) or
                any(any(ind in link for ind in blog_indicators) for link in links)
            )
            if not has_blog:
                signals.append("No blog, articles, or content section detected — no content marketing presence")

            # 3. Generic/weak service descriptions
            service_detail_words = [
                "specialized", "expert", "experience", "professional", "certified",
                "quality", "trusted", "years", "dedicated", "advanced"
            ]
            has_service_detail = any(word in page_text_lower for word in service_detail_words)
            if not has_service_detail:
                signals.append("Service descriptions appear generic or minimal — not differentiated")

            # 4. No testimonials or social proof
            proof_indicators = [
                "review", "testimonial", "patient said", "customer said",
                "client said", "rated", "star", "happy client", "success story"
            ]
            has_proof = any(ind in page_text_lower for ind in proof_indicators)
            if not has_proof:
                signals.append("No testimonials or social proof content found — missed trust signal")

            # 5. Generic headings
            headings = [h.get_text(strip=True).lower() for h in soup.find_all(["h1", "h2", "h3"])]
            generic_headings = ["welcome", "home", "about us", "our services", "contact us", "gallery"]
            non_generic = [h for h in headings[:5] if not any(g in h for g in generic_headings)]
            if headings and len(non_generic) == 0:
                signals.append("Page headings appear generic — no distinctive content strategy")

        except Exception:
            pass

        return signals, evidence
