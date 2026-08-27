import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Playwright, Browser, BrowserContext
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("browser.playwright")


class PlaywrightManager:
    """
    Singleton manager for headless Playwright browser instances.
    Reuses browser contexts with concurrency limits and resource blocking.
    """
    _instance: Optional["PlaywrightManager"] = None
    _lock = asyncio.Lock()

    def __init__(self):
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._semaphore = asyncio.Semaphore(settings.CRAWL_CONCURRENCY)
        self._is_initialized = False

    @classmethod
    async def get_instance(cls) -> "PlaywrightManager":
        if cls._instance is None:
            async with cls._lock:
                if cls._instance is None:
                    cls._instance = PlaywrightManager()
        return cls._instance

    async def initialize(self):
        if self._is_initialized and self._browser:
            return
        async with self._lock:
            if not self._is_initialized:
                try:
                    self._playwright = await async_playwright().start()
                    self._browser = await self._playwright.chromium.launch(
                        headless=True,
                        args=[
                            "--disable-gpu",
                            "--no-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-setuid-sandbox",
                            "--disable-extensions",
                        ]
                    )
                    self._is_initialized = True
                    logger.info("Playwright headless browser initialized successfully")
                except Exception as e:
                    logger.warning(f"Failed to initialize Playwright browser: {e}")
                    self._is_initialized = False

    async def fetch_rendered_html(self, url: str, timeout_sec: int = 15) -> Optional[str]:
        """
        Loads a page in a headless browser, waits for network idle / DOM content,
        and returns the fully rendered HTML.
        """
        if not self._is_initialized or not self._browser:
            await self.initialize()
            if not self._browser:
                return None

        async with self._semaphore:
            context: Optional[BrowserContext] = None
            try:
                context = await self._browser.new_context(
                    user_agent=settings.USER_AGENT,
                    viewport={"width": 1280, "height": 800},
                    java_script_enabled=True,
                    ignore_https_errors=True
                )
                
                # Block media/fonts to save bandwidth and speed up load
                await context.route(
                    "**/*.{png,jpg,jpeg,gif,svg,webp,mp4,webm,woff,woff2,ttf,eot}",
                    lambda route: route.abort()
                )

                page = await context.new_page()
                page.set_default_timeout(timeout_sec * 1000)

                await page.goto(url, wait_until="domcontentloaded", timeout=timeout_sec * 1000)
                # Brief wait for initial dynamic hydration if any
                await page.wait_for_timeout(1000)
                
                content = await page.content()
                await page.close()
                return content
            except Exception as e:
                logger.debug(f"Playwright rendering failed for {url}: {e}")
                return None
            finally:
                if context:
                    await context.close()

    async def shutdown(self):
        async with self._lock:
            if self._browser:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None
            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None
            self._is_initialized = False
            logger.info("Playwright browser manager shut down")
