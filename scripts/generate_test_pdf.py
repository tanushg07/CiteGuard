"""
Generates a synthetic but realistic single-column academic PDF for testing
the Days 2-3 extraction pipeline: numbered headings, multi-paragraph body
text, in-text citations (numbered + grouped + author-year), and a numbered
reference list.

This is NOT part of the shipped package -- it's a dev tool to produce
data/test_documents/doc_1_simple.pdf.
"""

from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen import canvas

PAGE_W, PAGE_H = LETTER
MARGIN = 72
LINE_H = 14
PARA_GAP = 26          # bigger than LINE_H so pdfplumber layout mode sees it as a paragraph break
HEADING_GAP_BEFORE = 32
HEADING_GAP_AFTER = 30  # must be >= PARA_GAP or the heading merges into the next paragraph's block


class PageWriter:
    def __init__(self, c):
        self.c = c
        self.y = PAGE_H - MARGIN
        self.x = MARGIN
        self.width = PAGE_W - 2 * MARGIN

    def _wrap(self, text, font="Helvetica", size=10):
        self.c.setFont(font, size)
        words = text.split()
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if self.c.stringWidth(trial, font, size) <= self.width:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def heading(self, text):
        self.y -= HEADING_GAP_BEFORE
        self._ensure_space(LINE_H)
        self.c.setFont("Helvetica-Bold", 12)
        self.c.drawString(self.x, self.y, text)
        self.y -= HEADING_GAP_AFTER

    def paragraph(self, text):
        lines = self._wrap(text)
        for line in lines:
            self._ensure_space(LINE_H)
            self.c.setFont("Helvetica", 10)
            self.c.drawString(self.x, self.y, line)
            self.y -= LINE_H
        self.y -= PARA_GAP

    def title(self, text):
        self.c.setFont("Helvetica-Bold", 16)
        self.c.drawString(self.x, self.y, text)
        self.y -= 24

    def _ensure_space(self, needed):
        if self.y - needed < MARGIN:
            self.c.showPage()
            self.y = PAGE_H - MARGIN
            self.c.setFont("Helvetica", 10)


def build(path):
    c = canvas.Canvas(path, pagesize=LETTER)
    w = PageWriter(c)

    w.title("Evaluating Retrieval-Augmented Verification for Scientific Claims")
    w.paragraph("A. Researcher, B. Scholar, C. Analyst -- Dept. of Computer Science, Example University")

    w.heading("Abstract")
    w.paragraph(
        "Automated fact verification systems increasingly rely on retrieval-augmented "
        "pipelines to ground claims in evidence. In this work we present a hybrid "
        "verification architecture combining sparse and dense retrieval with an "
        "ensemble of natural language inference models. We show that citation-graph "
        "reasoning further improves precision on a benchmark of scientific claims."
    )

    w.heading("1. Introduction")
    w.paragraph(
        "Citation misuse is a persistent problem in scientific writing [1]. Prior "
        "studies have shown that a significant fraction of citations do not "
        "support the claims they are attached to [2, 3]. This finding has been "
        "replicated across multiple domains (Smith et al., 2020)."
    )
    w.paragraph(
        "Automated citation verification has therefore attracted growing interest. "
        "Early approaches relied on simple lexical overlap between a claim and its "
        "cited source [4]. More recent work uses neural entailment models to assess "
        "whether a source actually supports a claim [5, 6]."
    )

    w.heading("2. Related Work")
    w.paragraph(
        "Evidence retrieval for fact verification has been studied extensively in "
        "the context of the FEVER shared task [7]. Cross-encoder re-ranking has been "
        "shown to substantially improve retrieval precision over bag-of-words "
        "baselines [8]."
    )
    w.paragraph(
        "Natural language inference models, particularly those fine-tuned on MNLI, "
        "have become the standard tool for entailment-based verification [9, 10]."
    )

    w.heading("3. Methodology")
    w.paragraph(
        "Our pipeline consists of four stages: document processing, evidence "
        "retrieval, verification, and reporting. Document processing extracts "
        "claim-citation pairs from the source PDF, preserving page and paragraph "
        "provenance for later auditing."
    )
    w.paragraph(
        "Evidence retrieval combines BM25 with a dense SBERT retriever, followed by "
        "cross-encoder re-ranking of the top candidates. Verification applies an "
        "ensemble of two MNLI models and a numerical consistency checker for "
        "claims involving statistics."
    )

    w.heading("4. Results")
    w.paragraph(
        "On our held-out evaluation set, the hybrid pipeline achieved 87.3% "
        "agreement with human annotators, compared to 74.1% for a lexical-overlap "
        "baseline. Citation-graph reasoning improved precision by an additional "
        "4.2 points on claims with multiple grouped citations."
    )

    w.heading("5. Discussion")
    w.paragraph(
        "These results suggest that combining retrieval-based evidence gathering "
        "with graph-based cross-citation checks meaningfully improves verification "
        "quality, particularly for claims supported by grouped citations rather "
        "than a single source."
    )

    w.heading("6. Conclusion")
    w.paragraph(
        "We presented a hybrid citation verification pipeline and demonstrated its "
        "effectiveness on a benchmark of scientific claims. Future work will "
        "explore extending the approach to multi-document claim verification."
    )

    w.heading("References")
    refs = [
        "J. Doe, \"Citation accuracy in scientific literature,\" Journal of Scientometrics, 2018.",
        "A. Lee and B. Kim, \"How often do citations support their claims?,\" Proc. ACL, 2019.",
        "M. Chen, \"A survey of citation misuse,\" Information Processing and Management, 2021.",
        "R. Patel, \"Lexical overlap methods for citation checking,\" EMNLP, 2017.",
        "S. Gupta et al., \"Neural entailment for citation verification,\" NAACL, 2021.",
        "T. Nguyen, \"Scaling entailment models for fact checking,\" ACL, 2022.",
        "J. Thorne et al., \"FEVER: a large-scale dataset for fact extraction and verification,\" NAACL, 2018.",
        "W. Zhao, \"Cross-encoder re-ranking for retrieval,\" SIGIR, 2020.",
        "Y. Liu et al., \"RoBERTa: a robustly optimized BERT pretraining approach,\" arXiv, 2019.",
        "P. He et al., \"DeBERTa: decoding-enhanced BERT with disentangled attention,\" ICLR, 2021.",
    ]
    for i, r in enumerate(refs, start=1):
        w.paragraph(f"[{i}] {r}")

    c.save()


if __name__ == "__main__":
    import sys
    build(sys.argv[1] if len(sys.argv) > 1 else "doc_1_simple.pdf")
    print("done")
