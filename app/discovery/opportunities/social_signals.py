from typing import List, Tuple, Dict, Optional


class SocialSignalDetector:
    """
    Analyzes discovered social profiles for quality signals.
    Detects potential Social Media Management opportunities.
    """

    def detect(
        self,
        social_profiles: Dict[str, Optional[str]],
        business_name: Optional[str] = None,
        website_domain: Optional[str] = None,
    ) -> Tuple[List[str], List[str]]:
        """
        Returns (signals, evidence_urls) tuple.
        social_profiles: dict of platform -> url (or None if not found)
        """
        signals = []
        evidence = []

        found_profiles = {k: v for k, v in social_profiles.items() if v}
        key_platforms = ["instagram", "facebook", "linkedin"]
        missing_platforms = [p for p in key_platforms if not social_profiles.get(p)]

        # 1. No social presence at all
        if not found_profiles:
            signals.append("No public social media profiles discovered — no online community presence")
            return signals, evidence

        # Collect evidence URLs
        for platform, url in found_profiles.items():
            if url:
                evidence.append(url)

        # 2. Missing major platforms
        if "instagram" not in found_profiles and "facebook" not in found_profiles:
            signals.append("No Instagram or Facebook presence found — major social platforms absent")
        elif len(missing_platforms) >= 2:
            missing_str = ", ".join(missing_platforms)
            signals.append(f"Missing social presence on key platforms: {missing_str}")

        # 3. Branding consistency — check handle vs business name
        if business_name and found_profiles:
            name_words = [
                w for w in business_name.lower().split()
                if len(w) > 3 and w not in ("the", "and", "for", "with")
            ]
            inconsistent = []
            for platform, url_val in found_profiles.items():
                if url_val and name_words:
                    url_lower = url_val.lower()
                    # If none of the meaningful name words appear in the profile URL
                    if not any(word in url_lower for word in name_words):
                        inconsistent.append(platform)
            if len(inconsistent) >= 2:
                platforms_str = ", ".join(inconsistent)
                signals.append(
                    f"Social handles appear inconsistent with business name on: {platforms_str} — branding fragmentation"
                )

        # 4. Website-social mismatch
        if website_domain and found_profiles:
            domain_root = website_domain.split(".")[0].lower() if "." in website_domain else website_domain.lower()
            if len(domain_root) > 3:
                all_profile_text = " ".join(u for u in found_profiles.values() if u).lower()
                if domain_root not in all_profile_text:
                    signals.append(
                        "Social profile handles don't match website domain — potential brand inconsistency"
                    )

        return signals, evidence
