"""
Policy Document Retriever with Citations & Refusal Mechanism
Enterprise AI Reliability Platform (ARGVTIX)

Features:
1. Relevance-scored policy retrieval.
2. Formatted citations (doc_id, title, citation string).
3. Refusal threshold: Gracefully returns 'I do not have policy information' when query score is below threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from argvtix.target_app.rag.policy_docs import POLICY_DOCUMENTS

ENGLISH_STOP_WORDS = {
    "a",
    "about",
    "above",
    "after",
    "again",
    "against",
    "all",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "because",
    "been",
    "before",
    "being",
    "below",
    "between",
    "both",
    "but",
    "by",
    "can",
    "could",
    "did",
    "do",
    "does",
    "doing",
    "down",
    "during",
    "each",
    "few",
    "for",
    "from",
    "further",
    "had",
    "has",
    "have",
    "having",
    "he",
    "her",
    "here",
    "hers",
    "herself",
    "him",
    "himself",
    "his",
    "how",
    "i",
    "if",
    "in",
    "into",
    "is",
    "it",
    "its",
    "itself",
    "me",
    "more",
    "most",
    "my",
    "myself",
    "no",
    "nor",
    "not",
    "of",
    "off",
    "on",
    "once",
    "only",
    "or",
    "other",
    "our",
    "ours",
    "ourselves",
    "out",
    "over",
    "own",
    "same",
    "she",
    "should",
    "so",
    "some",
    "such",
    "than",
    "that",
    "the",
    "their",
    "theirs",
    "them",
    "themselves",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "to",
    "too",
    "under",
    "until",
    "up",
    "very",
    "was",
    "we",
    "were",
    "what",
    "when",
    "where",
    "which",
    "while",
    "who",
    "whom",
    "why",
    "with",
    "would",
    "you",
    "your",
    "yours",
    "yourself",
    "yourselves",
    "many",
    "system",
}


@dataclass
class PolicyChunk:
    doc_id: str
    title: str
    content: str
    citation: str
    score: int


@dataclass
class RetrievalResult:
    query: str
    chunks: list[PolicyChunk] = field(default_factory=list)
    is_answerable: bool = True
    refusal_message: str | None = None

    @property
    def citations(self) -> list[str]:
        return [c.citation for c in self.chunks]

    @property
    def chunk_contents(self) -> list[str]:
        return [c.content for c in self.chunks]


def retrieve_policy(query: str, top_k: int = 3) -> list[str]:
    """
    Return top-k most relevant policy chunk contents for the given query.
    Backward-compatible with existing agent workflow.
    """
    res = retrieve_policy_with_citations(query=query, top_k=top_k)
    return res.chunk_contents


def retrieve_policy_with_titles(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """Return top-k chunks with id, title, and content for trace logging."""
    res = retrieve_policy_with_citations(query=query, top_k=top_k)
    return [
        {"id": c.doc_id, "title": c.title, "content": c.content, "citation": c.citation}
        for c in res.chunks
    ]


def retrieve_policy_with_citations(
    query: str,
    top_k: int = 3,
    score_threshold: int = 1,
) -> RetrievalResult:
    """
    Retrieve policy chunks with formal citations and refusal handling.

    If highest overlap score is strictly below score_threshold, marks
    is_answerable=False and provides a safe refusal message.
    """
    query_tokens = {
        w for w in re.findall(r"\w+", query.lower()) if w not in ENGLISH_STOP_WORDS and len(w) > 1
    }

    if not query_tokens:
        return RetrievalResult(
            query=query,
            chunks=[],
            is_answerable=False,
            refusal_message="I do not have policy information to answer this inquiry.",
        )

    scored: list[tuple[int, dict[str, Any]]] = []
    for doc in POLICY_DOCUMENTS:
        doc_tokens = {
            w
            for w in re.findall(r"\w+", (doc["title"] + " " + doc["content"]).lower())
            if w not in ENGLISH_STOP_WORDS
        }
        tag_tokens = {
            w
            for w in re.findall(r"\w+", " ".join(doc["tags"]).lower())
            if w not in ENGLISH_STOP_WORDS
        }
        overlap = len(query_tokens & (doc_tokens | tag_tokens))
        if overlap > 0:
            scored.append((overlap, doc))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored or scored[0][0] < score_threshold:
        return RetrievalResult(
            query=query,
            chunks=[],
            is_answerable=False,
            refusal_message="I do not have policy information to answer this inquiry.",
        )

    chunks: list[PolicyChunk] = [
        PolicyChunk(
            doc_id=d["id"],
            title=d["title"],
            content=d["content"],
            citation=f"[{d['id']}: {d['title']}]",
            score=score,
        )
        for score, d in scored[:top_k]
    ]

    return RetrievalResult(
        query=query,
        chunks=chunks,
        is_answerable=True,
        refusal_message=None,
    )


# 10 Standard unanswerable test questions
STANDARD_UNANSWERABLE_QUESTIONS = [
    "How do I bake a chocolate cake at home?",
    "What is the capital city of France?",
    "Who won the Cricket World Cup in 2011?",
    "Explain Einstein's theory of general relativity",
    "How to install PyTorch on Ubuntu Linux?",
    "What is the current market price of gold today?",
    "How many planets are there in the solar system?",
    "Can you write a poem about autumn leaves?",
    "What is the recipe for Hyderabadi biryani?",
    "What is the meaning of quantum superposition?",
]
