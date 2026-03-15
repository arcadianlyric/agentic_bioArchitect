"""
PubMed E-utilities search tool for Researcher agent.
Direct API call to NCBI Entrez.
"""

import os
import requests
import xml.etree.ElementTree as ET
from typing import List, Dict
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import get_api_key


ENTREZ_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def search_pubmed(query: str, max_results: int = 10) -> List[Dict]:
    """
    Search PubMed and return article summaries.

    Args:
        query: PubMed search query
        max_results: Maximum number of results

    Returns:
        List of dicts with keys: pmid, title, authors, journal, year, abstract
    """
    email = os.getenv("PUBMED_EMAIL", "user@example.com")

    # Step 1: esearch to get PMIDs
    search_url = f"{ENTREZ_BASE}/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmax": max_results,
        "sort": "relevance",
        "retmode": "json",
        "email": email,
    }
    resp = requests.get(search_url, params=search_params, timeout=15)
    resp.raise_for_status()
    pmids = resp.json().get("esearchresult", {}).get("idlist", [])

    if not pmids:
        return []

    # Step 2: efetch to get article details
    fetch_url = f"{ENTREZ_BASE}/efetch.fcgi"
    fetch_params = {
        "db": "pubmed",
        "id": ",".join(pmids),
        "rettype": "xml",
        "retmode": "xml",
        "email": email,
    }
    resp = requests.get(fetch_url, params=fetch_params, timeout=30)
    resp.raise_for_status()

    return _parse_pubmed_xml(resp.text)


def _parse_pubmed_xml(xml_text: str) -> List[Dict]:
    """Parse PubMed XML response into structured article data."""
    articles = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    for article_elem in root.findall(".//PubmedArticle"):
        try:
            medline = article_elem.find("MedlineCitation")
            pmid = medline.findtext("PMID", "")
            art = medline.find("Article")

            title = art.findtext("ArticleTitle", "")

            # Authors
            author_list = art.find("AuthorList")
            authors = []
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last = author.findtext("LastName", "")
                    first = author.findtext("ForeName", "")
                    if last:
                        authors.append(f"{last} {first}".strip())

            # Journal and year
            journal_elem = art.find("Journal")
            journal = journal_elem.findtext("Title", "") if journal_elem is not None else ""
            pub_date = journal_elem.find("JournalIssue/PubDate") if journal_elem is not None else None
            year = pub_date.findtext("Year", "") if pub_date is not None else ""

            # Abstract
            abstract_elem = art.find("Abstract")
            abstract = ""
            if abstract_elem is not None:
                abstract_parts = abstract_elem.findall("AbstractText")
                abstract = " ".join(
                    (p.text or "") for p in abstract_parts
                )

            articles.append({
                "pmid": pmid,
                "title": title,
                "authors": ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "journal": journal,
                "year": year,
                "abstract": abstract[:500],
            })
        except Exception:
            continue

    return articles


def search_umi_16s(topic: str = "UMI 16S rRNA metatranscriptomics") -> List[Dict]:
    """Convenience search for UMI 16S rRNA related papers."""
    query = f"({topic}) AND (2023:2026[pdat])"
    return search_pubmed(query, max_results=10)
