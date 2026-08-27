from typing import List, Optional
from pydantic import BaseModel, Field


class ServiceOpportunity(BaseModel):
    """A detected potential service opportunity based on observable public signals."""
    service: str            # normalized key: 'seo', 'social_media', 'branding', etc.
    service_display: str    # human-readable: 'SEO', 'Social Media', etc.
    confidence: str         # 'high', 'medium', 'low'
    signals: List[str] = Field(default_factory=list)   # observable signal descriptions
    evidence: List[str] = Field(default_factory=list)  # source URLs
    reason: str = ""        # concise human-readable reason (1 sentence)


class OpportunityResult(BaseModel):
    """Complete opportunity analysis result for a single candidate business."""
    has_opportunities: bool = False
    opportunities: List[ServiceOpportunity] = Field(default_factory=list)
    analyzed_services: List[str] = Field(default_factory=list)

    def get_short_reason(self) -> str:
        """Generate a brief summary of all detected opportunities."""
        if not self.opportunities:
            return ""
        service_names = [o.service_display for o in self.opportunities]
        if len(service_names) == 1:
            opp = self.opportunities[0]
            return f"Potential {opp.service_display} opportunity: {opp.reason}"
        names_str = ", ".join(service_names[:-1]) + f" and {service_names[-1]}"
        return f"Potential opportunities in: {names_str}"

    def top_opportunities(self, limit: int = 3) -> List[ServiceOpportunity]:
        """Return top N opportunities sorted by confidence."""
        order = {"high": 0, "medium": 1, "low": 2}
        sorted_opps = sorted(self.opportunities, key=lambda o: order.get(o.confidence, 3))
        return sorted_opps[:limit]
