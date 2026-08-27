import asyncio
from typing import List, Dict, Optional, Set
from dataclasses import dataclass
import httpx
from app.core.config import settings
from app.core.logging import get_logger
from app.core.rate_limit import DomainRateLimiter
from app.utils.urls import extract_domain, normalize_url
from app.discovery.browser.page_loader import PageLoader
from app.discovery.website.robots import RobotsInspector
from app.discovery.website.sitemap import SitemapParser
from app.discovery.website.url_discovery import URLDiscovery

logger = get_logger("website.crawler")


@dataclass
class CrawledPage:
    url: str
    html: str
    is_root: bool = False


class WebsiteCrawler:
    """
    Controlled, rate-limited website crawler.
    Inspects robots.txt, leverages sitemaps, discovers high-priority pages,
    and coordinates fast HTTP + Playwright hybrid loading.
    """
    def __init__(self, enable_playwright: bool = True):
        self.enable_playwright = enable_playwright
        self.page_loader = PageLoader(enable_playwright=enable_playwright)
        self.robots_inspector = RobotsInspector()
        self.sitemap_parser = SitemapParser()
        self.url_discovery = URLDiscovery()
        self.domain_limiter = DomainRateLimiter(min_delay=0.5)

    async def crawl_domain(
        self,
        start_url: str,
        max_pages: Optional[int] = None
    ) -> List[CrawledPage]:
        if max_pages is None:
            max_pages = settings.MAX_PAGES_PER_DOMAIN

        norm_start = normalize_url(start_url)
        domain = extract_domain(norm_start)
        if not domain:
            return []

        crawled_pages: List[CrawledPage] = []
        visited_urls: Set[str] = set()
        queue: List[str] = [norm_start]

        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }

        async with httpx.AsyncClient(headers=headers, timeout=settings.REQUEST_TIMEOUT, follow_redirects=True, verify=False) as client:
            # 1. Robots.txt Inspection & Sitemap Discovery
            robots_info = await self.robots_inspector.inspect(norm_start, client=client)
            robots_parser = robots_info.get("parser")
            declared_sitemaps = robots_info.get("sitemaps", [])

            # Check if root is disallowed
            if not self.robots_inspector.can_fetch(robots_parser, norm_start):
                logger.debug(f"Crawling disallowed by robots.txt for {norm_start}")
                return []

            # 2. Sitemap URL Discovery
            sitemap_urls = await self.sitemap_parser.discover_sitemap_urls(
                norm_start,
                declared_sitemaps=declared_sitemaps,
                client=client
            )
            for s_url in sitemap_urls:
                if s_url not in queue:
                    queue.append(s_url)

            # 3. Controlled Priority Crawl
            while queue and len(crawled_pages) < max_pages:
                current_url = queue.pop(0)
                if current_url in visited_urls:
                    continue
                visited_urls.add(current_url)

                if not self.robots_inspector.can_fetch(robots_parser, current_url):
                    continue

                try:
                    await self.domain_limiter.acquire(domain)
                    html_text, final_url = await self.page_loader.fetch_page(current_url, client=client)
                    
                    if not html_text:
                        continue

                    is_root = (normalize_url(final_url or current_url) == norm_start)
                    crawled_pages.append(CrawledPage(
                        url=final_url or current_url,
                        html=html_text,
                        is_root=is_root
                    ))

                    # Discover additional priority links if still under budget
                    if len(crawled_pages) < max_pages:
                        new_links = self.url_discovery.extract_internal_links(
                            html_text,
                            current_url=final_url or current_url,
                            max_links=5
                        )
                        for link in new_links:
                            if link not in visited_urls and link not in queue:
                                queue.append(link)

                except Exception as e:
                    logger.debug(f"Failed crawling {current_url}: {e}")
                    continue

        return crawled_pages
