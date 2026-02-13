import asyncio
from typing import Callable, Any, Optional, Type
from loguru import logger
from functools import wraps


async def retry_async(
    func: Callable,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
    on_retry: Optional[Callable] = None
) -> Any:
    """
    Retry an async function with exponential backoff

    Args:
        func: Async function to retry
        max_attempts: Maximum number of attempts
        delay: Initial delay between retries in seconds
        backoff: Backoff multiplier
        exceptions: Tuple of exceptions to catch
        on_retry: Optional callback called on retry (receives attempt number and exception)

    Returns:
        Result of successful function call

    Raises:
        Last exception if all attempts fail
    """
    current_delay = delay
    last_exception = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            logger.warning(
                f"Attempt {attempt}/{max_attempts} failed: {e}. "
                f"Retrying in {current_delay}s..."
            )

            if on_retry:
                await on_retry(attempt, e)

            if attempt < max_attempts:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
            else:
                logger.error(f"All {max_attempts} attempts failed")
                raise last_exception


def retry_decorator(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying async functions

    Usage:
        @retry_decorator(max_attempts=3, delay=1.0)
        async def my_function():
            ...
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_async(
                lambda: func(*args, **kwargs),
                max_attempts=max_attempts,
                delay=delay,
                backoff=backoff,
                exceptions=exceptions
            )
        return wrapper
    return decorator
