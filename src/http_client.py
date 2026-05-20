import time
from collections import defaultdict
from threading import Lock
from urllib.parse import urlparse

import httpx

USER_AGENT = (
    "JobSearchSystem/0.1 (personal use; contact jigar.work712@gmail.com)"
)

# Some hosts (Workday, YC, Wellfound, Cloudflare-fronted sites) reject the
# polite UA. Use a real browser string for those.
BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
)

BROWSER_HEADERS = {
    "User-Agent": BROWSER_UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    # NB: deliberately not requesting 'br' (brotli) — httpx core doesn't decompress
    # it without the optional 'brotli' package, and we don't want the extra dep.
    "Accept-Encoding": "gzip, deflate",
}

_host_locks: dict[str, Lock] = defaultdict(Lock)
_last_request: dict[str, float] = defaultdict(float)
MIN_INTERVAL_SECONDS = 1.0


def _polite_wait(url: str) -> None:
    host = urlparse(url).netloc
    with _host_locks[host]:
        elapsed = time.monotonic() - _last_request[host]
        if elapsed < MIN_INTERVAL_SECONDS:
            time.sleep(MIN_INTERVAL_SECONDS - elapsed)
        _last_request[host] = time.monotonic()


def get(url: str, *, timeout: float = 20.0, headers: dict | None = None,
        max_retries: int = 3, **kwargs) -> httpx.Response:
    """Polite per-host GET with exponential backoff on 5xx and 429."""
    hdrs = {"User-Agent": USER_AGENT}
    if headers:
        hdrs.update(headers)

    last_exc: Exception | None = None
    for attempt in range(max_retries):
        _polite_wait(url)
        try:
            resp = httpx.get(url, timeout=timeout, headers=hdrs, follow_redirects=True, **kwargs)
        except httpx.RequestError as e:
            last_exc = e
            time.sleep(2**attempt)
            continue
        if resp.status_code < 400:
            return resp
        if resp.status_code in (429, 500, 502, 503, 504) and attempt < max_retries - 1:
            time.sleep(2**attempt)
            continue
        resp.raise_for_status()
    if last_exc:
        raise last_exc
    raise RuntimeError(f"GET {url} failed after {max_retries} attempts")
