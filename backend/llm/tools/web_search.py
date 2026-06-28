import logging

import httpx

from config import SEARXNG_URL, TAVILY_API_KEY, WEB_SEARCH_BACKEND

logger = logging.getLogger("tools.web_search")


async def run_web_search(query: str, num_results: int = 5) -> list[dict]:
    try:
        if WEB_SEARCH_BACKEND == "tavily":
            return await _tavily_search(query, num_results)
        return await _searxng_search(query, num_results)
    except Exception as e:
        raise RuntimeError(f"web_search failed: {e}") from e


async def _searxng_search(query: str, num_results: int) -> list[dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(
            f"{SEARXNG_URL}/search",
            params={"q": query, "format": "json", "categories": "general"},
        )
        resp.raise_for_status()
        data = resp.json()
    if "error" in data:
        raise RuntimeError(f"SearXNG error: {data['error']}")
    results = []
    for r in data.get("results", [])[:num_results]:
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        })
    return results


async def _tavily_search(query: str, num_results: int) -> list[dict]:
    if not TAVILY_API_KEY:
        raise RuntimeError("TAVILY_API_KEY is not set — configure it or switch WEB_SEARCH_BACKEND to searxng")
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query, "max_results": num_results},
        )
        resp.raise_for_status()
        data = resp.json()
    results = []
    for r in data.get("results", [])[:num_results]:
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "snippet": r.get("content", ""),
        })
    return results
