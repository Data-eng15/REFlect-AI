"""
Domain classifier for REFlect AI domain-aware routing.

A zero-dependency, multi-label keyword-frequency classifier that detects a
paper's research domain(s) from its title and abstract. The detected domains
drive source routing (see DOMAIN_SOURCE_MAP and smart_retriever.py) so that we
only call the evidence APIs relevant to each paper instead of all nine.

No external model is required — scoring is pure keyword frequency, which keeps
the classifier deterministic, instant, and dependency-free.
"""
from __future__ import annotations

import re
from typing import List, Tuple

# ── Domain taxonomy ──────────────────────────────────────────────────────────
# Each domain maps to a list of indicative keywords / phrases. Multi-word
# phrases are matched as substrings (case-insensitive) so "neural network"
# and "machine learning" are detected as single signals.
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "computer_science": [
        "algorithm", "neural network", "deep learning", "machine learning",
        "software", "artificial intelligence", " ai ", "nlp", "transformer",
        "llm", "large language model", "benchmark", "dataset",
        "reinforcement learning",
    ],
    "medicine": [
        "clinical", "patient", "disease", "therapy", "treatment", "drug",
        "hospital", "diagnosis", "biomedical", "cancer", "trial",
        "randomized", "randomised", "vaccine",
    ],
    "finance": [
        "market", "financial", "investment", "stock", "economic", "revenue",
        "portfolio", "trading", "fintech", "cryptocurrency", "equity",
    ],
    "law": [
        "legal", "legislation", "regulation", "policy", "court", "judicial",
        "compliance", "governance", "jurisdiction",
    ],
    "engineering": [
        "manufacturing", "mechanical", "electrical", "civil", "structural",
        "materials", "robotics", "automation", "hardware", "sensor",
    ],
    "social_science": [
        "social", "psychological", "behavioral", "behavioural", "survey",
        "sociology", "anthropology", "education", "cognitive",
    ],
    "biology": [
        "genomics", "protein", "cell", "molecular", "gene", "organism",
        "ecology", "evolution", "microbiology",
    ],
}

# ── Source routing config ────────────────────────────────────────────────────
# ── Source vocabulary (aligned to the live retrieval_node tasks) ─────────────
# Core sources are ALWAYS queried, regardless of discipline:
#   - Semantic Scholar / OpenAlex carry citation signal for any field;
#   - Google Patents is a primary REF impact pathway (commercial/industrial
#     translation) and is relevant across every discipline — a machine-learning
#     method is just as patentable as a chemical process — so it is never
#     skipped. Domain routing only gates the remaining *optional* sources.
CORE_SOURCES: list[str] = ["semantic_scholar", "openalex_fallback", "openalex_enrichment", "patents"]
OPTIONAL_SOURCES: list[str] = ["github", "pubmed", "clinical_trials", "soft_sciences"]
ALL_SOURCES: list[str] = CORE_SOURCES + OPTIONAL_SOURCES

# Maps each detected domain to the *optional* sources worth calling for it.
# (Core sources — incl. patents — are added automatically.) "general" routes
# to everything.
DOMAIN_SOURCE_MAP: dict[str, list[str]] = {
    "computer_science": ["github"],
    "medicine":         ["pubmed", "clinical_trials"],
    "finance":          ["soft_sciences"],
    "law":              ["soft_sciences"],
    "engineering":      ["github"],
    "social_science":   ["soft_sciences"],
    "biology":          ["pubmed", "clinical_trials"],
    "general":          list(OPTIONAL_SOURCES),
}

# Maps OpenAlex concept/field display names (lower-cased substrings) → our domain
# taxonomy, so routing can be driven by a researcher's *profile* fields.
FIELD_DOMAIN_MAP: dict[str, str] = {
    "computer science": "computer_science", "artificial intelligence": "computer_science",
    "machine learning": "computer_science", "artificial neural network": "computer_science",
    "data science": "computer_science", "information retrieval": "computer_science",
    "medicine": "medicine", "internal medicine": "medicine", "oncology": "medicine",
    "surgery": "medicine", "pathology": "medicine", "immunology": "medicine",
    "psychiatry": "medicine", "pharmacology": "medicine", "cardiology": "medicine",
    "biology": "biology", "genetics": "biology", "biochemistry": "biology",
    "molecular biology": "biology", "microbiology": "biology", "neuroscience": "biology",
    "economics": "finance", "finance": "finance", "financial economics": "finance",
    "law": "law", "political science": "law", "public administration": "law",
    "engineering": "engineering", "mechanical engineering": "engineering",
    "electrical engineering": "engineering", "materials science": "engineering",
    "robotics": "engineering", "control theory": "engineering",
    "sociology": "social_science", "psychology": "social_science",
    "education": "social_science", "social psychology": "social_science",
}


def fields_to_domains(fields: list[str]) -> list[str]:
    """Map a researcher's OpenAlex fields/concepts to our domain taxonomy.

    Returns an ordered, de-duplicated list of domain keys. Empty if no field
    matches (caller should treat that as ``general`` / full fallback)."""
    domains: list[str] = []
    for f in fields or []:
        fl = (f or "").lower().strip()
        for needle, domain in FIELD_DOMAIN_MAP.items():
            if needle in fl and domain not in domains:
                domains.append(domain)
                break
    return domains


def sources_for_domain_keys(domains: list[str]) -> list[str]:
    """Core sources + the union of optional sources for the given domain keys."""
    out: list[str] = list(CORE_SOURCES)
    if not domains:
        return list(ALL_SOURCES)
    for d in domains:
        for src in DOMAIN_SOURCE_MAP.get(d, []):
            if src not in out:
                out.append(src)
    return out

# Confidence thresholds.
MIN_DOMAIN_CONFIDENCE = 0.15   # below this a domain is not reported at all
LOW_CONFIDENCE_CUTOFF = 0.40   # top domain below this flags low_confidence

# Saturation constant: the number of weighted keyword occurrences at which a
# domain reaches full (1.0) confidence. Calibrated so that a paper containing
# ~5 weighted domain-keyword hits is treated as a confident match, while one or
# two stray hits stay below the 0.40 routing cutoff. (A flat hits/total-keywords
# ratio is too harsh in practice — real papers rarely hit 40% of a keyword set.)
CONFIDENCE_SATURATION = 5.0


def _count_hits(text: str, keywords: list[str], title_text: str) -> int:
    """Count total weighted keyword occurrences (frequency) in ``text``.

    Every occurrence of a domain keyword counts once; occurrences inside the
    title are weighted double, since the title is the strongest domain signal.
    Returns an integer weighted hit count.
    """
    hits = 0
    for kw in keywords:
        occ_all = text.count(kw)        # occurrences across title + abstract
        occ_title = title_text.count(kw)  # title occurrences counted a second time
        hits += occ_all + occ_title
    return hits


def classify_domain(title: str, abstract: str = "") -> List[Tuple[str, float]]:
    """Classify the research domain(s) of a paper from its title and abstract.

    Scoring is keyword-frequency based: for each domain we count how many times
    its keywords occur in the (lower-cased) title + abstract, with title matches
    weighted double. Confidence is ``hits / total_keywords_in_domain`` clamped to
    ``[0, 1]`` — so keyword-rich papers saturate toward 1.0 while thin signals
    stay low and trigger fallback.

    Args:
        title: Paper title (required).
        abstract: Paper abstract (optional but strongly improves accuracy).

    Returns:
        A list of ``(domain, confidence)`` tuples sorted by confidence
        descending, including only domains scoring above
        :data:`MIN_DOMAIN_CONFIDENCE`. If nothing clears the threshold, returns
        ``[("general", 1.0)]`` which triggers the full-source fallback.

    Example:
        >>> classify_domain("Deep learning for stock market prediction")
        [("computer_science", 0.57), ("finance", 0.36)]
    """
    title_l = f" {(title or '').lower()} "
    abstract_l = f" {(abstract or '').lower()} "
    combined = title_l + abstract_l

    scored: list[Tuple[str, float]] = []
    for domain, keywords in DOMAIN_KEYWORDS.items():
        hits = _count_hits(combined, keywords, title_l)
        if hits == 0:
            continue
        confidence = min(1.0, hits / CONFIDENCE_SATURATION)
        if confidence > MIN_DOMAIN_CONFIDENCE:
            scored.append((domain, round(confidence, 3)))

    if not scored:
        return [("general", 1.0)]

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored


def is_low_confidence(domains: List[Tuple[str, float]]) -> bool:
    """Return True if the top detected domain is below the confidence cutoff.

    A low-confidence result means the classifier is unsure of the domain, so the
    caller should fall back to querying all sources rather than a narrow subset.
    """
    if not domains:
        return True
    top_domain, top_conf = domains[0]
    if top_domain == "general":
        return True
    return top_conf < LOW_CONFIDENCE_CUTOFF


def sources_for_domains(domains: List[Tuple[str, float]]) -> List[str]:
    """Return the de-duplicated union of source whitelists for the given domains.

    Only domains at or above :data:`LOW_CONFIDENCE_CUTOFF` contribute their
    whitelist; weaker secondary domains are ignored to keep routing tight. If no
    domain qualifies, returns the full "general" source set.
    """
    qualifying = [d for d, conf in domains if conf >= LOW_CONFIDENCE_CUTOFF]
    if not qualifying:
        return list(ALL_SOURCES)
    return sources_for_domain_keys(qualifying)


def plan_routing(fields: list[str] | None = None, title: str = "", abstract: str = "") -> dict:
    """Decide which evidence sources to query for a researcher and/or a paper.

    Phase-2 "dynamic gravity": routing is driven primarily by the researcher's
    *profile* fields, with the paper's own classified domain layered on top — so
    a CS professor analysing a paper that was, say, cited in a medical context
    still picks up the relevant sources (the "twist"). Core scholarly sources are
    always included; recall is protected at retrieval time by an
    insufficient-evidence fallback to the full source set.

    Returns a metadata dict describing the decision (visible in the UI).
    """
    profile_domains = fields_to_domains(fields or [])
    paper_scored = classify_domain(title, abstract) if title else []
    paper_domains = [d for d, c in paper_scored if c >= LOW_CONFIDENCE_CUTOFF and d != "general"]

    combined: list[str] = []
    for d in profile_domains + paper_domains:
        if d not in combined:
            combined.append(d)

    if not combined:
        sources_called = list(ALL_SOURCES)
        reason = "no_clear_domain"
    else:
        sources_called = sources_for_domain_keys(combined)
        if profile_domains and paper_domains:
            reason = "profile+paper"
        elif profile_domains:
            reason = "profile"
        else:
            reason = "paper"

    sources_skipped = [s for s in ALL_SOURCES if s not in sources_called]
    return {
        "profile_domains": profile_domains,
        "paper_domains": paper_domains,
        "domains": combined,
        "sources_called": sources_called,
        "sources_skipped": sources_skipped,
        "all_sources": list(ALL_SOURCES),
        "reason": reason,
        "saved_calls": len(sources_skipped),
    }
