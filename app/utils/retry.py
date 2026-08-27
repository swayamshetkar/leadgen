import asyncio
import functools
import logging
from typing import Type, Tuple

logger = logging.getLogger(__name__)


def async_retry(
    retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for retrying async functions with exponential backoff.
    """
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            for attempt in range(1, retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt == retries:
                        logger.warning(
                            f"Function {func.__name__} failed after {retries} attempts: {e}"
                        )
                        raise
                    logger.debug(
                        f"Attempt {attempt} for {func.__name__} failed ({e}), "
                        f"retrying in {current_delay:.2f}s..."
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            if last_exception:
                raise last_exception
        return wrapper
    return decorator
