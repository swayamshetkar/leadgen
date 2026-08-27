from typing import Optional, Set
from app.models.candidate import CandidateBusiness
from app.discovery.normalization.business import BusinessNormalizer
from app.discovery.normalization.phone import PhoneNormalizer
from app.utils.text import similarity_ratio


class CandidateMatcher:
    """
    Multi-tier business candidate matcher.
    Evaluates whether two candidate records represent the same real-world business entity.
    """

    def is_match(self, c1: CandidateBusiness, c2: CandidateBusiness) -> bool:
        # Tier 1: Exact Domain Match
        if c1.domain and c2.domain and c1.domain == c2.domain:
            return True
        if c1.domain and c2.domain and c1.domain != c2.domain:
            return False

        # Tier 2: Exact Phone Match
        p1_keys = self._get_phone_keys(c1)
        p2_keys = self._get_phone_keys(c2)
        if p1_keys and p2_keys and (p1_keys & p2_keys):
            return True

        # Tier 3: Shared Social Profile Handle
        s1_profiles = self._get_social_profiles(c1)
        s2_profiles = self._get_social_profiles(c2)
        if s1_profiles and s2_profiles and (s1_profiles & s2_profiles):
            return True

        # Tier 4: Business Match Key + Shared Location
        name_key1 = BusinessNormalizer.match_key(c1.name)
        name_key2 = BusinessNormalizer.match_key(c2.name)
        locs1 = {loc.lower().strip() for loc in c1.locations if loc}
        locs2 = {loc.lower().strip() for loc in c2.locations if loc}
        shared_location = bool(locs1 & locs2) or not locs1 or not locs2

        if name_key1 and name_key2 and name_key1 == name_key2 and shared_location:
            return True

        # Tier 5: High Fuzzy Name Similarity + Shared Location
        if c1.name and c2.name and shared_location:
            ratio = similarity_ratio(c1.name, c2.name)
            if ratio >= 0.88 and len(c1.name) >= 5 and len(c2.name) >= 5:
                return True

        return False

    def _get_phone_keys(self, cand: CandidateBusiness) -> Set[str]:
        keys = set()
        for p in cand.phone_numbers:
            k = PhoneNormalizer.digits_key(p.value)
            if k:
                keys.add(k)
        return keys

    def _get_social_profiles(self, cand: CandidateBusiness) -> Set[str]:
        profiles = set()
        for platform, url in cand.social_profiles.items():
            if url:
                clean_url = url.lower().strip()
                clean_url = clean_url.replace("http://", "").replace("https://", "").replace("www.", "").rstrip("/")
                profiles.add(f"{platform}:{clean_url}")
        return profiles
