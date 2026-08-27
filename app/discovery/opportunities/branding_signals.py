from typing import List, Tuple, Dict, Optional
from bs4 import BeautifulSoup


class BrandingSignalDetector:
    """
    Detects branding inconsistency and weakness signals across public properties.
    Detects potential Branding / Visual Identity opportunities.
    """

    def detect(
        self,
        business_name: Optional[str],
        domain: Optional[str],
        social_profiles: Dict[str, Optional[str]],
        html: str = "",
        url: str = "",
    ) -> Tuple[List[str], List[str]]:
        """
        Returns (signals, evidence_urls) tuple.
        """
        signals = []
        evidence = [url] if url else []

        if not business_name:
            signals.append("Business name not clearly identified — weak brand identity")
            return signals, evidence

        name_lower = business_name.lower().strip()
        name_words = [
            w for w in name_lower.split()
            if len(w) > 3 and w not in ("the", "and", "for", "with", "clinic", "centre", "center")
        ]

        # 1. Domain vs business name consistency
        if domain:
            domain_root = domain.split(".")[0].lower().replace("-", "").replace("_", "")
            name_no_spaces = name_lower.replace(" ", "").replace("-", "").replace(".", "")

            name_in_domain = (
                any(word in domain_root for word in name_words) or
                any(domain_root in word for word in name_words) or
                # Check if abbreviation-style match (e.g. "ABC Dental" -> "abcd")
                len(domain_root) >= 3 and domain_root in name_no_spaces
            )
            if not name_in_domain and len(domain_root) > 3:
                signals.append(
                    f"Business name '{business_name}' doesn't clearly match domain '{domain}' — inconsistent brand identity"
                )

        # 2. Social profiles naming consistency
        found_profiles = {k: v for k, v in social_profiles.items() if v}
        if found_profiles and name_words:
            inconsistent_count = 0
            for platform, url_val in found_profiles.items():
                if url_val:
                    url_lower = url_val.lower()
                    if not any(word in url_lower for word in name_words):
                        inconsistent_count += 1
            if inconsistent_count > 0 and len(found_profiles) > 0:
                ratio = inconsistent_count / len(found_profiles)
                if ratio > 0.4:
                    signals.append(
                        "Multiple social profiles have handles inconsistent with business name — fragmented brand identity"
                    )

        # 3. Website visual identity signals
        if html:
            try:
                soup = BeautifulSoup(html, "lxml")

                # Check for logo
                logo_by_class = soup.find_all(
                    "img",
                    attrs={"class": lambda c: c and "logo" in " ".join(c if isinstance(c, list) else [c]).lower()}
                )
                logo_by_alt = soup.find_all(
                    "img",
                    attrs={"alt": lambda a: a and "logo" in a.lower()}
                )
                logo_in_text = soup.find_all("img", attrs={"id": lambda i: i and "logo" in i.lower()})
                if not logo_by_class and not logo_by_alt and not logo_in_text:
                    signals.append("No logo image detected on website — missing key brand element")

                # Check for style/CSS
                style_tags = soup.find_all("style")
                external_css = soup.find_all("link", attrs={"rel": "stylesheet"})
                inline_style_chars = sum(
                    len(s.string or "") for s in style_tags
                )
                if not external_css and inline_style_chars < 200:
                    signals.append("Minimal styling detected — website may appear generic or unbranded")

            except Exception:
                pass

        return signals, evidence
