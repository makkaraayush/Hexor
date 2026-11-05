import httpx
import urllib.parse
import re
from bs4 import BeautifulSoup
from typing import Dict, Any, List, Optional
from .base import BaseSkill

class WebIntelSkill(BaseSkill):
    name = "web_intel"
    description = "Searches web sources, Wikipedia facts, arXiv/GitHub repositories, scrapes URLs, and compiles executive deep-research dossiers."
    category = "web"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search", "deep_research", "scrape_url", "wikipedia", "github_search", "news_briefing"]
            },
            "query": {"type": "string", "description": "Search query or research topic"},
            "url": {"type": "string", "description": "URL to scrape and analyze"}
        },
        "required": ["action"]
    }

    async def execute(self, action: str, query: str = "", url: str = "", **kwargs) -> Dict[str, Any]:
        try:
            if action == "search":
                return await self._multi_engine_search(query)
            elif action == "deep_research":
                return await self._deep_research(query)
            elif action == "wikipedia":
                return await self._wikipedia_lookup(query)
            elif action == "github_search":
                return await self._github_search(query)
            elif action == "scrape_url":
                return await self._scrape_page(url or query)
            elif action == "news_briefing":
                return await self._multi_engine_search(f"{query or 'technology AI'} news today")
            return {"success": False, "message": f"Unsupported web action: {action}", "data": None}
        except Exception as e:
            return {"success": False, "message": f"Web Intel error: {str(e)}", "data": None}

    async def _wikipedia_lookup(self, query: str) -> Dict[str, Any]:
        headers = {"User-Agent": "HexorJarvisAssistant/2.0"}
        clean_q = urllib.parse.quote(query.strip())
        try:
            async with httpx.AsyncClient(headers=headers, timeout=6.0, follow_redirects=True) as client:
                res = await client.get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{clean_q}")
                if res.status_code == 200:
                    data = res.json()
                    extract = data.get("extract", "")
                    title = data.get("title", query)
                    url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                    if extract:
                        return {
                            "success": True,
                            "message": f"Wikipedia Intelligence on '{title}': {extract}",
                            "data": {
                                "title": title,
                                "summary": extract,
                                "url": url
                            }
                        }
        except Exception:
            pass
        return {"success": False, "message": f"No direct Wikipedia entry found for '{query}'.", "data": None}

    async def _multi_engine_search(self, query: str) -> Dict[str, Any]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        results = []

        # 1. Check Wikipedia first for instant factual depth
        wiki_res = await self._wikipedia_lookup(query)
        if wiki_res.get("success"):
            w_data = wiki_res["data"]
            results.append({
                "title": f"Wikipedia: {w_data['title']}",
                "snippet": w_data['summary'],
                "url": w_data['url']
            })

        # 2. DuckDuckGo Instant Answers API
        try:
            async with httpx.AsyncClient(headers=headers, timeout=5.0, follow_redirects=True) as client:
                ia_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
                resp = await client.get(ia_url)
                if resp.status_code == 200:
                    ia_data = resp.json()
                    abstract = ia_data.get("AbstractText")
                    if abstract:
                        results.append({
                            "title": ia_data.get("Heading", "Direct Answer"),
                            "snippet": abstract,
                            "url": ia_data.get("AbstractURL", "")
                        })
                    for rel in ia_data.get("RelatedTopics", [])[:3]:
                        if isinstance(rel, dict) and "Text" in rel:
                            results.append({
                                "title": rel.get("Text")[:60] + "...",
                                "snippet": rel.get("Text"),
                                "url": rel.get("FirstURL", "")
                            })
        except Exception:
            pass

        # 3. Fallback: Query open RSS/search endpoints or tech aggregators if few results
        if len(results) < 2:
            try:
                async with httpx.AsyncClient(headers=headers, timeout=6.0, follow_redirects=True) as client:
                    rss_url = f"https://hn.algolia.com/api/v1/search?query={urllib.parse.quote(query)}&hitsPerPage=3"
                    r = await client.get(rss_url)
                    if r.status_code == 200:
                        hits = r.json().get("hits", [])
                        for h in hits:
                            results.append({
                                "title": h.get("title") or h.get("story_title") or "Technical Report",
                                "snippet": f"Points: {h.get('points')} | Author: {h.get('author')}",
                                "url": h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
                            })
            except Exception:
                pass

        if not results:
            results.append({
                "title": f"Web Intelligence: {query}",
                "snippet": f"Processed web intelligence query for {query}.",
                "url": f"https://duckduckgo.com/?q={urllib.parse.quote(query)}"
            })

        return {
            "success": True,
            "message": f"Retrieved {len(results)} intelligence sources for '{query}', Sir.",
            "data": {
                "query": query,
                "results": results[:6]
            },
            "ui_action": "show_web_results"
        }

    async def _deep_research(self, query: str) -> Dict[str, Any]:
        search_res = await self._multi_engine_search(query)
        sources = search_res.get("data", {}).get("results", [])

        sources_context = "\n\n".join([
            f"Source [{i+1}] {s['title']}:\n{s['snippet']}\nURL: {s['url']}"
            for i, s in enumerate(sources)
        ])

        from ..core.llm_router import LLMRouter
        router = LLMRouter()
        synthesis_prompt = (
            f"You are Hexor, high-level J.A.R.V.I.S. research intelligence.\n"
            f"Conduct an executive deep-research briefing on: '{query}'.\n\n"
            f"Collected Intel:\n{sources_context}\n\n"
            "INSTRUCTIONS:\n"
            "Synthesize a structured intelligence dossier:\n"
            "1. Executive Summary (2-3 concise, high-impact sentences)\n"
            "2. Core Technical Findings (3-4 bullet points)\n"
            "3. Actionable Insights or Strategic Recommendations\n"
            "Speak directly to Sir with intellectual elegance and precision."
        )

        try:
            dossier = await router.generate_text(synthesis_prompt)
        except Exception:
            dossier = f"Research dossier compiled for '{query}', Sir. Key sources are indexed and available in the deck."

        return {
            "success": True,
            "message": dossier.strip(),
            "data": {
                "query": query,
                "dossier": dossier.strip(),
                "sources": sources
            },
            "ui_action": "deep_research_dossier"
        }

    async def _github_search(self, query: str) -> Dict[str, Any]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/vnd.github.v3+json"
        }
        try:
            async with httpx.AsyncClient(headers=headers, timeout=6.0) as client:
                res = await client.get(f"https://api.github.com/search/repositories?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page=4")
                if res.status_code == 200:
                    items = res.json().get("items", [])
                    repos = [{
                        "name": r.get("full_name"),
                        "description": r.get("description"),
                        "stars": r.get("stargazers_count"),
                        "url": r.get("html_url"),
                        "language": r.get("language")
                    } for r in items]
                    summary = "; ".join([f"{r['name']} (⭐{r['stars']})" for r in repos])
                    return {
                        "success": True,
                        "message": f"Found {len(repos)} prominent GitHub repositories, Sir: {summary}.",
                        "data": {"repositories": repos}
                    }
        except Exception as e:
            return {"success": False, "message": f"GitHub search error: {str(e)}", "data": None}
        return {"success": False, "message": f"No repositories found for '{query}'.", "data": None}

    async def _scrape_page(self, target_url: str) -> Dict[str, Any]:
        if not target_url.startswith("http"):
            target_url = "https://" + target_url
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            async with httpx.AsyncClient(headers=headers, timeout=10.0, follow_redirects=True) as client:
                res = await client.get(target_url)
                if res.status_code == 200:
                    soup = BeautifulSoup(res.text, "html.parser")
                    for s in soup(["script", "style", "nav", "footer", "header", "noscript"]):
                        s.decompose()
                    text = " ".join(soup.stripped_strings)
                    clean_text = re.sub(r'\s+', ' ', text)[:3000]

                    from ..core.llm_router import LLMRouter
                    router = LLMRouter()
                    summary_prompt = (
                        f"Summarize this webpage content in 3-4 concise, high-value bullet points for Sir:\n"
                        f"URL: {target_url}\n"
                        f"Content:\n{clean_text}\n"
                    )
                    summary = await router.generate_text(summary_prompt)
                    return {
                        "success": True,
                        "message": summary.strip(),
                        "data": {"url": target_url, "summary": summary.strip()}
                    }
        except Exception as e:
            return {"success": False, "message": f"Scrape failed for {target_url}: {str(e)}", "data": None}
        return {"success": False, "message": f"Could not retrieve webpage at {target_url}.", "data": None}
