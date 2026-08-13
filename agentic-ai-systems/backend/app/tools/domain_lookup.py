"""
Cheap, offline domain-credibility signal used by the Source Evaluator agent as one
input among several (age of domain via TLD heuristics, known-good/known-bad lists).
This is intentionally NOT a call to a paid credibility API -- see docs/write-up.md 3.5.
"""
from __future__ import annotations

import tldextract

HIGH_TRUST_SUFFIXES = {"gov", "edu"}
HIGH_TRUST_DOMAINS = {
    "nature.com", "nih.gov", "who.int", "reuters.com", "apnews.com",
    "nasa.gov", "arxiv.org", "acm.org", "ieee.org",
}
LOW_TRUST_MARKERS = {"blogspot.", "wordpress.com", "medium.com/@"}


def domain_lookup(url: str) -> dict:
    ext = tldextract.extract(url)
    registered_domain = f"{ext.domain}.{ext.suffix}" if ext.suffix else ext.domain
    signal = "neutral"
    if ext.suffix in HIGH_TRUST_SUFFIXES or registered_domain in HIGH_TRUST_DOMAINS:
        signal = "high_trust"
    elif any(marker in url for marker in LOW_TRUST_MARKERS):
        signal = "low_trust"
    return {"domain": registered_domain, "signal": signal}
