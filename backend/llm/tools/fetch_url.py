import ipaddress
import logging
import socket
import ssl
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("tools.fetch_url")

_MAX_BYTES   = 1_000_000  # hard byte cap before HTML parsing
_ALLOWED_PORTS = {80, 443, None}  # None = scheme default
_ALLOWED_CT  = frozenset({"text/html", "text/plain", "application/xhtml+xml"})


def _resolve_and_validate(hostname: str) -> tuple[str | None, str | None]:
    """Resolve hostname, reject any non-public IP. Returns (error, first_ip)."""
    try:
        infos = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
    except socket.gaierror as e:
        return f"Rejected: could not resolve '{hostname}': {e}", None
    for info in infos:
        raw = info[4][0]
        try:
            ip = ipaddress.ip_address(raw)
        except ValueError:
            continue
        if (ip.is_loopback or ip.is_private or ip.is_link_local or
                ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return f"Rejected: '{hostname}' resolves to non-public address {raw}", None
    if not infos:
        return f"Rejected: no addresses resolved for '{hostname}'", None
    return None, infos[0][4][0]


def _validate_url(url: str) -> tuple[str | None, str | None]:
    """Validate scheme, port, and hostname IP. Returns (error, validated_ip)."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return f"Rejected: scheme '{parsed.scheme}' not allowed (only http/https)", None
    if not parsed.hostname:
        return "Rejected: missing hostname", None
    if parsed.port not in _ALLOWED_PORTS:
        return f"Rejected: port {parsed.port} not allowed (only 80 or 443)", None
    return _resolve_and_validate(parsed.hostname)


async def _pinned_fetch(url: str, hostname: str, ip: str) -> tuple[httpx.Response, bytes]:
    """
    Connect directly to pre-resolved IP to close DNS rebinding TOCTOU gap.
    - sni_hostname extension passes original hostname to SSL so cert verification
      and SNI use the domain name, not the IP literal.
    - Body is streamed and capped at _MAX_BYTES (byte-level) to prevent memory
      exhaustion; Content-Length is checked before reading when present.
    """
    parsed = urlparse(url)
    scheme = parsed.scheme
    port   = parsed.port or (443 if scheme == "https" else 80)
    ip_host = f"[{ip}]" if ":" in ip else ip
    path   = (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")
    target = f"{scheme}://{ip_host}:{port}{path}"

    ssl_ctx = ssl.create_default_context() if scheme == "https" else None

    async with httpx.AsyncClient(
        verify=ssl_ctx if ssl_ctx is not None else True,
        follow_redirects=False,
        timeout=httpx.Timeout(15.0),
    ) as client:
        req = client.build_request(
            "GET", target,
            headers={"Host": hostname, "User-Agent": "Mozilla/5.0"},
        )
        # Pin SSL SNI + cert verification to original hostname, not the IP literal
        if scheme == "https":
            req.extensions["sni_hostname"] = hostname.encode("ascii")

        resp = await client.send(req, stream=True)
        try:
            # Redirects: return with empty body; caller re-validates the new URL
            if resp.is_redirect:
                return resp, b""

            # Reject oversized responses before reading
            cl = resp.headers.get("content-length")
            if cl:
                try:
                    if int(cl) > _MAX_BYTES:
                        return resp, b""
                except (ValueError, TypeError):
                    pass

            # Stream body, cap on raw bytes (not decoded chars) to prevent exhaustion
            chunks: list[bytes] = []
            total = 0
            async for chunk in resp.aiter_bytes():
                chunks.append(chunk)
                total += len(chunk)
                if total >= _MAX_BYTES:
                    break
            return resp, b"".join(chunks)
        finally:
            await resp.aclose()


async def run_fetch_url(url: str) -> str:
    err, ip = _validate_url(url)
    if err:
        logger.warning("[fetch_url] blocked url=%s reason=%s", url, err)
        return err

    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return "Error: beautifulsoup4 not installed"

    current_url      = url
    current_hostname = urlparse(url).hostname
    current_ip       = ip

    try:
        for _hop in range(5):
            resp, body = await _pinned_fetch(current_url, current_hostname, current_ip)

            if resp.is_redirect:
                location = resp.headers.get("location", "")
                if not location.startswith(("http://", "https://")):
                    p = urlparse(current_url)
                    location = f"{p.scheme}://{p.netloc}{location}"
                hop_err, hop_ip = _validate_url(location)
                if hop_err:
                    logger.warning("[fetch_url] redirect blocked url=%s reason=%s", location, hop_err)
                    return f"Rejected redirect: {hop_err}"
                current_url      = location
                current_hostname = urlparse(location).hostname
                current_ip       = hop_ip
                continue

            resp.raise_for_status()
            break

        if not body:
            return f"Could not extract content from {url} (empty or oversized response)"

        ct = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        if ct and ct not in _ALLOWED_CT:
            return f"Rejected: content type '{ct}' not supported (expected HTML or plain text)"

        soup = BeautifulSoup(body, "lxml")
        title_tag  = soup.find("title")
        title_text = title_tag.get_text(strip=True) if title_tag else ""
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

        if not text.strip():
            return f"Could not extract text content from {current_url}"

        header = (
            f"Title: {title_text}\nURL: {current_url}\n\n"
            if title_text and title_text != current_url
            else f"URL: {current_url}\n\n"
        )
        return header + text[:8000]

    except httpx.HTTPStatusError as e:
        return f"HTTP error fetching {url}: {e.response.status_code}"
    except Exception as e:
        logger.warning("[fetch_url] fetch failed url=%s err=%s", url, e)
        return f"Error fetching {url}: {e}"
