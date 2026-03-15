"""
Tavily web search tool for Researcher agent.
Direct API call (not through CrewAI tool abstraction).
"""

import os
import requests
from typing import List, Dict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_api_key


def search(query: str, max_results: int = 5, search_depth: str = "advanced") -> List[Dict]:
    """
    Search the web using Tavily API.

    Args:
        query: Search query string
        max_results: Maximum number of results to return
        search_depth: "basic" or "advanced"

    Returns:
        List of result dicts with keys: title, url, content, score
    """
    api_key = get_api_key("TAVILY_API_KEY")
    url = "https://api.tavily.com/search"

    payload = {
        "api_key": api_key,
        "query": query,
        "max_results": max_results,
        "search_depth": search_depth,
        "include_answer": True,
    }

    resp = requests.post(url, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    results = []
    for r in data.get("results", []):
        results.append({
            "title": r.get("title", ""),
            "url": r.get("url", ""),
            "content": r.get("content", ""),
            "score": r.get("score", 0),
        })

    return {
        "answer": data.get("answer", ""),
        "results": results,
    }


def search_papers(topic: str, year_range: str = "2023-2026") -> Dict:
    """Search for bioinformatics papers and tools on a specific topic."""
    query = f"{topic} bioinformatics tools papers {year_range}"
    return search(query, max_results=5, search_depth="advanced")
