import urllib.robotparser
import urllib.parse
from typing import List, Optional
import httpx
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("website.robots")


class RobotsInspector:
    """
    Inspects publicly declared robots.txt rules and sitemap directives.
    Ensures crawler respects site permissions and discovers declared sitemap files.
    """
    def __init__(self, user_agent: str = "*"):
        self.user_agent = user_agent

    async def inspect(
        self,
        base_url: str,
        client: Optional[httpx.AsyncClient] = None
    ) -> dict:
        """
        Returns {
            'sitemaps': list[str],
            'parser': RobotFileParser or None,
            'is_allowed_root': bool
        }
        """
        parsed = urllib.parse.urlparse(base_url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
        
        sitemaps: List[str] = []
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(robots_url)

        close_client = False
        if client is None:
            client = httpx.AsyncClient(timeout=10.0, verify=False)
            close_client = True

        try:
            resp = await client.get(robots_url)
            if resp.status_code == 200:
                lines = resp.text.splitlines()
                rp.parse(lines)

                # Extract sitemap directives explicitly
                for line in lines:
                    line_clean = line.strip()
                    if line_clean.lower().startswith("sitemap:"):
                        sitemap_url = line_clean.split(":", 1)[1].strip()
                        if sitemap_url and sitemap_url not in sitemaps:
                            sitemaps.append(sitemap_url)
            else:
                # If robots.txt doesn't exist, all public pages are assumed allowed
                rp.allow_all = True

        except Exception as e:
            logger.debug(f"Could not fetch robots.txt for {base_url}: {e}")
            rp.allow_all = True
        finally:
            if close_client:
                await client.aclose()

        is_allowed_root = rp.can_fetch(self.user_agent, base_url) if rp else True

        return {
            "sitemaps": sitemaps,
            "parser": rp,
            "is_allowed_root": is_allowed_root
        }

    def can_fetch(self, parser: Optional[urllib.robotparser.RobotFileParser], url: str) -> bool:
        if parser is None or getattr(parser, "allow_all", False):
            return True
        try:
            return parser.can_fetch(self.user_agent, url)
        except Exception:
            return True
