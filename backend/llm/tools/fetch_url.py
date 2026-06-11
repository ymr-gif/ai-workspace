import ipaddress
import logging
import socket
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("tools.fetch_url")

_MAX_BYTES = 1_000_000  # 1 MB response cap before stripping


def _validate_url(url: str) -> str | None:
    """Return error string if URL is unsafe, else None."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return f"Rejected: scheme '{parsed.scheme}' not allowed (only http/https)"
    hostname = parsed.hostname
    if not hostname:
        return "Rejected: missing hostname"
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        return f"Rejected: could not resolve hostname '{hostname}': {e}"
    for info in infos:
        addr = info[4][0]
        try:
            ip = ipaddress.ip_address(addr)
        except ValueError:
            continue
        if (
            ip.is_loopback
            or ip.is_private
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            return f"Rejected: '{hostname}' resolves to non-public address {addr}"
    return None


async def run_fetch_url(url: str) -> str:
    err = _validate_url(url)
    if err:
        logger.warning("[fetch_url] blocked url=%s reason=%s", url, err)
        return err

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "Error: beautifulsoup4 not installed"

    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=False,
            max_redirects=0,
        ) as client:
            resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})

            # Follow redirects manually so each hop is re-validated
            hops = 0
            while resp.is_redirect and hops < 5:
                location = resp.headers.get("location", "")
                if not location.startswith(("http://", "https://")):
                    # relative redirect — reconstruct absolute
                    base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
                    location = base + location
                hop_err = _validate_url(location)
                if hop_err:
                    logger.warning("[fetch_url] redirect blocked url=%s reason=%s", location, hop_err)
                    return f"Rejected redirect: {hop_err}"
                resp = await client.get(location, headers={"User-Agent": "Mozilla/5.0"})
                url = location
                hops += 1

            resp.raise_for_status()

        raw = resp.text[:_MAX_BYTES]
        soup = BeautifulSoup(raw, "lxml")
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else ""
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        if not text.strip():
            return f"Could not extract text content from {url}"

        header = f"Title: {title_text}\nURL: {url}\n\n" if title_text and title_text != url else f"URL: {url}\n\n"
        return header + text[:8000]

    except httpx.HTTPStatusError as e:
        return f"HTTP error fetching {url}: {e.response.status_code}"
    except Exception as e:
        logger.warning("[fetch_url] fetch failed url=%s err=%s", url, e)
        return f"Error fetching {url}: {e}"
