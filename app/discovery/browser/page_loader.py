import re
from typing import Optional, Tuple
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.discovery.browser.playwright_manager import PlaywrightManager
from app.utils.urls import normalize_url

logger = get_logger("browser.page_loader")


class PageLoader:
    """
    Hybrid page loader.
    Fetches raw HTML via high-performance async HTTPX first.
    If the page requires client-side JavaScript rendering (SPA shell, blank body),
    it transparently falls back to Playwright headless rendering.
    """
    def __init__(self, enable_playwright: bool = True):
        self.enable_playwright = enable_playwright
        self.headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }

    async def fetch_page(
        self,
        url: str,
        client: Optional[httpx.AsyncClient] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Returns (html_content, final_url).
        """
        normalized = normalize_url(url)
        if not normalized:
            return None, None

        close_client = False
        if client is None:
            client_kwargs = {
                "headers": self.headers,
                "timeout": settings.REQUEST_TIMEOUT,
                "follow_redirects": True,
                "verify": False,
            }
            if settings.PROXY_URL:
                client_kwargs["proxy"] = settings.PROXY_URL
            client = httpx.AsyncClient(**client_kwargs)
            close_client = True

        try:
            resp = await client.get(normalized)
            if resp.status_code == 200:
                content_type = resp.headers.get("content-type", "").lower()
                if "text/html" not in content_type and "application/xhtml" not in content_type:
                    return None, str(resp.url)

                html_text = resp.text
                final_url = str(resp.url)

                # Check if page is an empty SPA shell (e.g. <div id="root"></div> without text)
                if self.enable_playwright and self._needs_js_rendering(html_text):
                    logger.debug(f"Detected client-side JS app on {url}, executing Playwright fallback")
                    pw_manager = await PlaywrightManager.get_instance()
                    rendered_html = await pw_manager.fetch_rendered_html(final_url)
                    if rendered_html and len(rendered_html) > len(html_text):
                        return rendered_html, final_url

                return html_text, final_url
            else:
                logger.debug(f"HTTP fetch for {url} returned status {resp.status_code}")
                return None, None

        except Exception as e:
            logger.debug(f"HTTP fetch error for {url}: {e}")
            if self.enable_playwright:
                try:
                    pw_manager = await PlaywrightManager.get_instance()
                    rendered_html = await pw_manager.fetch_rendered_html(normalized)
                    if rendered_html:
                        return rendered_html, normalized
                except Exception:
                    pass
            return None, None

        finally:
            if close_client:
                await client.aclose()

    def _needs_js_rendering(self, html: str) -> bool:
        if not html or len(html) < 400:
            return True
        # Check if text length is very low compared to script tags
        has_spa_root = bool(re.search(r'<div\s+id=["\'](?:root|app|__next)["\']\s*>\s*</div>', html, re.IGNORECASE))
        has_noscript_warning = "enable javascript to run this app" in html.lower() or "javascript is required" in html.lower()
        return has_spa_root or has_noscript_warning
