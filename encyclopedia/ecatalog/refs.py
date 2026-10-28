from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from ecatalog.io import REFERENCES_MD, ROOT

CITE_RE = re.compile(r"\[(\d{1,2})\]")


@dataclass(frozen=True)
class BibliographyEntry:
    number: int
    title: str
    authors: str
    url: str


BIBLIOGRAPHY: dict[int, BibliographyEntry] = {
    1: BibliographyEntry(1, "STORM: Assisting in Writing Wikipedia-like Articles From Scratch with LLMs", "Shao et al., 2024", "https://arxiv.org/abs/2402.14207"),
    2: BibliographyEntry(2, "WikiChat: Stopping the Hallucination of LLM Chatbots by Few-Shot Grounding on Wikipedia", "Semnani et al., 2023", "https://arxiv.org/abs/2305.14292"),
    3: BibliographyEntry(3, "RARR: Researching and Revising What Language Models Say", "Gao et al., 2022", "https://arxiv.org/abs/2210.08726"),
    4: BibliographyEntry(4, "FActScore: Fine-grained Atomic Evaluation of Factual Precision", "Min et al., 2023", "https://arxiv.org/abs/2305.14251"),
    5: BibliographyEntry(5, "SAFE: Long-form factuality in large language models", "Wei et al., 2024", "https://arxiv.org/abs/2403.18802"),
    6: BibliographyEntry(6, "ALCE: Enabling LLMs to Generate Text with Citations", "Gao et al., 2023", "https://arxiv.org/abs/2305.14627"),
    7: BibliographyEntry(7, "Using LLMs for the Extraction and Normalization of Product Attribute Values (WDC-PAVE)", "Brinkmann et al., 2024", "https://arxiv.org/abs/2403.02130"),
    8: BibliographyEntry(8, "Self-Refinement Strategies for LLM-based Product Attribute Value Extraction", "Brinkmann & Bizer, 2025", "https://arxiv.org/abs/2501.01237"),
    9: BibliographyEntry(9, "Entity Matching using Large Language Models", "Peeters, Steiner & Bizer, 2023", "https://arxiv.org/abs/2310.11244"),
    10: BibliographyEntry(10, "Curate Before You Connect: Identity and Ontology Tagging in a Production KG", "2026", "https://arxiv.org/abs/2608.10644"),
    11: BibliographyEntry(11, "Zep: A Temporal Knowledge Graph Architecture for Agent Memory", "Rasmussen et al., 2025", "https://arxiv.org/abs/2501.13956"),
    12: BibliographyEntry(12, "GraphRAG: From Local to Global — A Graph RAG Approach to Query-Focused Summarization", "Edge et al., 2024", "https://arxiv.org/abs/2404.16130"),
    13: BibliographyEntry(13, "A-MEM: Agentic Memory for LLM Agents", "Xu et al., 2025", "https://arxiv.org/abs/2502.12110"),
    14: BibliographyEntry(14, "MemGPT: Towards LLMs as Operating Systems", "Packer et al., 2023", "https://arxiv.org/abs/2310.08560"),
    15: BibliographyEntry(15, "Gorilla: LLM Connected with Massive APIs", "Patil et al., 2023", "https://arxiv.org/abs/2305.15334"),
    16: BibliographyEntry(16, "ToolLLM / ToolBench: Facilitating LLMs to Master 16000+ Real-world APIs", "Qin et al., 2023", "https://arxiv.org/abs/2307.16789"),
    17: BibliographyEntry(17, "Voyager: An Open-Ended Embodied Agent with LLMs", "Wang et al., 2023", "https://arxiv.org/abs/2305.16291"),
    18: BibliographyEntry(18, "The AGNTCY Agent Directory Service", "2025", "https://arxiv.org/abs/2509.18787"),
    19: BibliographyEntry(19, "Skilldex: Package Manager and Registry for Agent Skill Packages", "2026", "https://arxiv.org/abs/2604.16911"),
    20: BibliographyEntry(20, "AI Agent-Driven Framework for Automated Product KG Construction in E-Commerce", "2025", "https://arxiv.org/abs/2511.11017"),
    21: BibliographyEntry(21, "Co-STORM: Into the Unknown Unknowns", "Jiang et al., 2024", "https://arxiv.org/abs/2408.15232"),
    22: BibliographyEntry(22, "MCP: Landscape, Security Threats, and Future Research Directions", "Hou et al., 2025", "https://arxiv.org/abs/2503.23278"),
}


def scan_cited_numbers(root: Path | None = None) -> set[int]:
    base = root or ROOT
    cited: set[int] = set()
    skip = {REFERENCES_MD.resolve()}
    for path in base.rglob("*"):
        if not path.is_file() or path.resolve() in skip:
            continue
        if path.suffix not in {".md", ".py", ".yaml", ".yml"}:
            continue
        for match in CITE_RE.finditer(path.read_text(encoding="utf-8")):
            n = int(match.group(1))
            if n in BIBLIOGRAPHY:
                cited.add(n)
    return cited


def render_references_md(numbers: set[int]) -> str:
    lines = [
        "# References",
        "",
        "Unique arXiv sources cited under `encyclopedia/` (inline markers `[n]`).",
        "",
        "## References",
        "",
    ]
    for n in sorted(numbers):
        e = BIBLIOGRAPHY[n]
        lines.append(f"[{n}] {e.title}. {e.authors}. {e.url}  ")
    lines.append("")
    return "\n".join(lines)


def check_references_sync() -> list[str]:
    expected = render_references_md(scan_cited_numbers())
    if not REFERENCES_MD.is_file():
        return ["missing REFERENCES.md (run: catalog references refresh)"]
    if REFERENCES_MD.read_text(encoding="utf-8") != expected:
        return ["REFERENCES.md out of sync (run: catalog references refresh)"]
    return []


def write_references_md() -> str:
    content = render_references_md(scan_cited_numbers())
    REFERENCES_MD.write_text(content, encoding="utf-8")
    return content
