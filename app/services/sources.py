"""Resolve supplied source documents; never treat the manuscript as evidence."""
import re


def sources_for_claim(claim, sources, references):
    marker = claim.citation_marker
    explicit = [s for s in sources if marker in s.get('markers', []) or
                marker == s.get('citation') or marker in s.get('name', '')]
    if explicit:
        return explicit
    # Explicitly mapped corpora must never be used for a different citation.
    unmapped = [s for s in sources if not s.get('markers')]
    if len({s['name'] for s in sources}) == 1 and unmapped:
        return unmapped
    reference = next((r for r in references if r.startswith(marker)), '')
    query = reference or (marker if not marker.startswith('[') else '')
    words = set(re.findall(r'[a-z]{3,}|\d{4}', query.lower())) - {'and', 'the', 'et', 'al'}
    matches = []
    for source in unmapped:
        title = set(re.findall(r'[a-z]{3,}|\d{4}', source['name'].lower()))
        if words and len(words & title) >= min(2, len(words)):
            matches.append(source)
    return matches
