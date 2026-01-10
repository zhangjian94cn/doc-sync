"""
Retry Module
Provides retry functionality for API calls with exponential backoff.
"""

import time
from functools import wraps
from typing import TypeVar, Callable, Optional, Tuple, Type
import requests

from src.logger import logger
from src.config import API_MAX_RETRIES, API_RETRY_BASE_DELAY


T = TypeVar('T')


def retry_on_failure(
    max_retries: int = API_MAX_RETRIES,
    base_delay: float = API_RETRY_BASE_DELAY,
    retryable_exceptions: Tuple[Type[Exception], ...] = (requests.exceptions.RequestException,),
    retryable_status_codes: Tuple[int, ...] = (429, 500, 502, 503, 504)
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied exponentially)
        retryable_exceptions: Tuple of exception types to retry on
        retryable_status_codes: HTTP status codes that should trigger a retry
        
    Returns:
        Decorated function with retry logic
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            last_exception: Optional[Exception] = None
            
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    
                    # Check for retriable HTTP response
                    if hasattr(result, 'status_code'):
                        if result.status_code in retryable_status_codes:
                            if attempt < max_retries:
                                delay = base_delay * (2 ** attempt)
                                logger.warning(f"收到 {result.status_code} 响应，{delay:.1f}s 后重试 ({attempt + 1}/{max_retries})")
                                time.sleep(delay)
                                continue
                            else:
                                logger.error(f"达到最大重试次数，最后状态: {result.status_code}")
                    
                    return result
                    
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        logger.warning(f"请求失败: {e}，{delay:.1f}s 后重试 ({attempt + 1}/{max_retries})")
                        time.sleep(delay)
                    else:
                        logger.error(f"达到最大重试次数，最后错误: {e}")
                        raise
            
            # This shouldn't be reached, but just in case
            if last_exception:
                raise last_exception
            return result  # type: ignore
            
        return wrapper
    return decorator


def api_request_with_retry(
    method: str,
    url: str,
    max_retries: int = API_MAX_RETRIES,
    base_delay: float = API_RETRY_BASE_DELAY,
    **kwargs
) -> requests.Response:
    """
    Make an HTTP request with automatic retry and exponential backoff.
    
    Args:
        method: HTTP method ('GET', 'POST', etc.)
        url: Request URL
        max_retries: Maximum retry attempts
        base_delay: Base delay between retries
        **kwargs: Additional arguments passed to requests
        
    Returns:
        Response object
        
    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    retryable_status_codes = {429, 500, 502, 503, 504}
    last_response: Optional[requests.Response] = None
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.request(method, url, timeout=kwargs.pop('timeout', 30), **kwargs)
            
            if response.status_code in retryable_status_codes:
                last_response = response
                if attempt < max_retries:
                    delay = base_delay * (2 ** attempt)
                    
                    # Check for Retry-After header
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            delay = max(delay, float(retry_after))
                        except ValueError:
                            pass
                    
                    logger.warning(f"API 请求收到 {response.status_code}，{delay:.1f}s 后重试")
                    time.sleep(delay)
                    continue
            
            return response
            
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                delay = base_delay * (2 ** attempt)
                logger.warning(f"API 请求失败: {e}，{delay:.1f}s 后重试")
                time.sleep(delay)
            else:
                raise
    
    # Return the last response if we exhausted retries on status codes
    if last_response is not None:
        return last_response
    
    raise requests.exceptions.RequestException("所有重试都失败了")


def retry_on_rate_limit(
    max_retries: int = API_MAX_RETRIES,
    base_delay: float = API_RETRY_BASE_DELAY
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying Feishu API calls on rate limit error (99991400).
    
    This decorator is specifically designed for lark_oapi SDK responses
    that return objects with success() method and code attribute.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds (will be multiplied exponentially)
        
    Returns:
        Decorated function with rate limit retry logic
        
    Usage:
        @retry_on_rate_limit(max_retries=3, base_delay=1.0)
        def list_document_blocks(self, document_id: str):
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            delay = base_delay
            last_result = None
            
            for attempt in range(max_retries):
                result = func(*args, **kwargs)
                last_result = result
                
                # Check if result has lark_oapi response structure
                if hasattr(result, 'success') and callable(result.success):
                    if result.success():
                        return result
                    
                    # Check for rate limit error code
                    code = getattr(result, 'code', None)
                    if code == 99991400:  # Rate limit
                        if attempt < max_retries - 1:
                            logger.warning(f"Rate limited (99991400), retrying in {delay:.1f}s... ({attempt + 1}/{max_retries})")
                            time.sleep(delay)
                            delay *= 2  # Exponential backoff
                            continue
                        else:
                            logger.error(f"Rate limit exceeded after {max_retries} retries")
                            return result
                    else:
                        # Non-rate-limit error, don't retry
                        return result
                else:
                    # Not a lark_oapi response, return as-is
                    return result
            
            return last_result  # Return last result if all retries exhausted
            
        return wrapper
    return decorator


def with_rate_limit_retry(func: Callable, *args, 
                          max_retries: int = API_MAX_RETRIES,
                          base_delay: float = API_RETRY_BASE_DELAY,
                          **kwargs):
    """
    Execute a function with rate limit retry logic.
    
    This is a functional alternative to the decorator for cases where
    you can't use decorators (e.g., dynamically calling different methods).
    
    Args:
        func: Function to call
        *args: Positional arguments for the function
        max_retries: Maximum retry attempts
        base_delay: Base delay in seconds
        **kwargs: Keyword arguments for the function
        
    Returns:
        The function's return value
    """
    delay = base_delay
    last_result = None
    
    for attempt in range(max_retries):
        result = func(*args, **kwargs)
        last_result = result
        
        # Check for lark_oapi response with rate limit error
        if hasattr(result, 'code') and result.code == 99991400:
            if attempt < max_retries - 1:
                logger.warning(f"Rate limited, retrying in {delay:.1f}s...")
                time.sleep(delay)
                delay *= 2
                continue
            else:
                logger.error(f"Rate limit exceeded after {max_retries} retries")
                return result
        else:
            return result
    
    return last_result

