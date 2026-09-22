"""
Stage 5 (Days 6-7), part 2: list[Claim] -> list[ClaimCitationPair].

This is the final output of the Document Processing module -- the exact
contract Evidence Retrieval (Jayant) and Verification (Dhanush) build on.

One ClaimCitationPair row is produced per (claim, citation mention) --
a sentence with two SEPARATE citations ("... [1] and also ... (Smith, 2020)")
produces two rows sharing the same claim_id and claim text. A single GROUPED
citation ("... [3, 7, 12]") stays as one row with one citation_id: the
grouping is preserved on the Citation object itself (its ref_ids list, from
citation_extractor.py), and it's Evidence Retrieval's job to resolve each
ref_id within that one citation_id to a source and gather evidence
accordingly -- not something we fan out at this stage.
"""

from __future__ import annotations

from citeguard.document_processing.claim_extractor import Claim
from citeguard.schemas import ClaimCitationPair


def build_claim_citation_pairs(claims: list[Claim]) -> list[ClaimCitationPair]:
    pairs: list[ClaimCitationPair] = []
    for claim in claims:
        for citation_id in claim.citation_ids:
            pairs.append(
                ClaimCitationPair(
                    claim_id=claim.claim_id,
                    claim=claim.text,
                    citation_id=citation_id,
                    page=claim.page,
                    paragraph=claim.paragraph,
                )
            )
    return pairs
