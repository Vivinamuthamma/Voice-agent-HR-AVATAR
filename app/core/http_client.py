import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

class AsyncHTTPClient:
    """Async HTTP client with connection pooling for external API calls."""

    def __init__(self, timeout: int = 30, max_connections: int = 10):
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.connector = aiohttp.TCPConnector(
            limit=max_connections,
            limit_per_host=max_connections,
            ttl_dns_cache=300,
            use_dns_cache=True,
            keepalive_timeout=60,
            enable_cleanup_closed=True
        )
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def start(self):
        """Initialize the HTTP session."""
        if self.session is None:
            self.session = aiohttp.ClientSession(
                connector=self.connector,
                timeout=self.timeout,
                trust_env=True  # Use environment proxy settings
            )
            logger.info("AsyncHTTPClient session started")

    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("AsyncHTTPClient session closed")

    @asynccontextmanager
    async def request_context(self, method: str, url: str, **kwargs):
        """Context manager for making HTTP requests with automatic retry."""
        if not self.session:
            await self.start()

        max_retries = kwargs.pop('max_retries', 3)
        retry_delay = kwargs.pop('retry_delay', 1.0)

        for attempt in range(max_retries):
            try:
                async with self.session.request(method, url, **kwargs) as response:
                    yield response
                break
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt < max_retries - 1:
                    logger.warning(f"Request attempt {attempt + 1} failed: {e}, retrying in {retry_delay}s")
                    await asyncio.sleep(retry_delay * (2 ** attempt))
                else:
                    logger.error(f"Request failed after {max_retries} attempts: {e}")
                    raise

    async def get(self, url: str, **kwargs) -> Dict[str, Any]:
        """Make a GET request."""
        async with self.request_context('GET', url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def post(self, url: str, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, **kwargs) -> Dict[str, Any]:
        """Make a POST request."""
        if json_data:
            kwargs['json'] = json_data
        elif data:
            kwargs['data'] = data

        async with self.request_context('POST', url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def post_stream(self, url: str, data: Optional[Dict[str, Any]] = None, json_data: Optional[Dict[str, Any]] = None, **kwargs):
        """Make a streaming POST request."""
        if json_data:
            kwargs['json'] = json_data
        elif data:
            kwargs['data'] = data

        async with self.request_context('POST', url, **kwargs) as response:
            response.raise_for_status()
            return response

# Global instance for reuse across the application
_http_client: Optional[AsyncHTTPClient] = None

def get_http_client() -> AsyncHTTPClient:
    """Get or create the global HTTP client instance."""
    global _http_client
    if _http_client is None:
        _http_client = AsyncHTTPClient()
    return _http_client

async def init_http_client():
    """Initialize the global HTTP client."""
    client = get_http_client()
    await client.start()

async def close_http_client():
    """Close the global HTTP client."""
    global _http_client
    if _http_client:
        await _http_client.close()
        _http_client = None
