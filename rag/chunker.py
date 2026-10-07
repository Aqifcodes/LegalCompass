"""
LegalCompass — Section-Aware Legal Chunker (v2)

Handles the India Code PDF format:
  "17. Time limit for payment of wages.—(1) The employer shall..."
  "CHAPTER III\nPAYMENT OF WAGES\n"

Key fixes over v1:
- Correctly detects "N. Title.—content" pattern used in all four Labour Codes
- Skips Table of Contents pages (pages where >60% of lines are TOC entries)
- Preserves full section content including all subsections
- Never creates heading-only chunks
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LegalChunk:
    text: str
    document_id: str
    document_title: str
    section_number: Optional[str]
    section_title: Optional[str]
    page: Optional[int]
    source_url: Optional[str]
    jurisdiction: Optional[str]
    document_type: Optional[str]
    chunk_index: int = 0

    def is_useful(self) -> bool:
        stripped = self.text.strip()
        if len(stripped) < 100:
            return False
        # Reject pure TOC entries (lots of dots or just numbers)
        printable = re.sub(r'[\s\d\.\-—()]', '', stripped)
        if len(printable) < 30:
            return False
        return True


# ---------------------------------------------------------------------------
# Patterns specific to India Code PDFs
# ---------------------------------------------------------------------------

# Matches: "17. Time limit for payment of wages.—" or "17. Short title.—"
# The em-dash (—) marks where the content begins
INDIA_CODE_SECTION = re.compile(
    r'^(\d+[A-Z]?)\.\s+([A-Z][^—\n]{5,120}?)\.?—',
    re.MULTILINE
)

# Chapter headings
CHAPTER_PATTERN = re.compile(
    r'^CHAPTER\s+[IVXLCDM]+\s*\n([A-Z][A-Z\s,&]+)',
    re.MULTILINE
)

# Page marker inserted by our extractor
PAGE_MARKER = re.compile(r'\[PAGE:(\d+)\]')

# Lines to strip (gazette boilerplate)
STRIP_PATTERNS = [
    re.compile(r'THE GAZETTE OF INDIA.*', re.IGNORECASE),
    re.compile(r'EXTRAORDINARY.*PART II.*', re.IGNORECASE),
    re.compile(r'MINISTRY OF LAW.*', re.IGNORECASE),
]

# TOC detection: line like "17. Time limit for payment of wages." with nothing after
TOC_LINE = re.compile(r'^\s*\d+[A-Z]?\.\s+[A-Z][^\n]{5,100}\.\s*$', re.MULTILINE)


class LegalChunker:
    MIN_CHUNK = 120
    MAX_CHUNK = 2500
    OVERLAP = 200

    def __init__(self, document_id, document_title, source_url=None,
                 jurisdiction=None, document_type=None):
        self.document_id = document_id
        self.document_title = document_title
        self.source_url = source_url
        self.jurisdiction = jurisdiction
        self.document_type = document_type

    def chunk(self, annotated_text: str) -> list[LegalChunk]:
        pages = self._split_pages(annotated_text)
        non_toc_pages = [(pnum, txt) for pnum, txt in pages
                         if not self._is_toc_page(txt)]
        full_text = '\n'.join(f'[PAGE:{pnum}]\n{txt}' for pnum, txt in non_toc_pages)
        sections = self._extract_sections(full_text)
        chunks = self._build_chunks(sections)
        return [c for c in chunks if c.is_useful()]

    # ------------------------------------------------------------------
    def _split_pages(self, text: str) -> list[tuple[int, str]]:
        parts = PAGE_MARKER.split(text)
        result = []
        i = 0
        current_page = 1
        while i < len(parts):
            if i == 0:
                if parts[i].strip():
                    result.append((current_page, parts[i]))
                i += 1
            else:
                try:
                    current_page = int(parts[i])
                    if i + 1 < len(parts):
                        result.append((current_page, parts[i + 1]))
                    i += 2
                except (ValueError, IndexError):
                    i += 1
        return result

    def _is_toc_page(self, text: str) -> bool:
        """Detect Table of Contents pages to skip them."""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if not lines:
            return False
        # A TOC page has many lines matching "N. Title." with nothing after
        toc_matches = sum(1 for l in lines if TOC_LINE.match(l + '\n'))
        # Also check for "ARRANGEMENT OF SECTIONS" header
        if 'ARRANGEMENT OF SECTIONS' in text.upper():
            return True
        # If >40% of non-empty lines look like TOC entries
        if lines and toc_matches / len(lines) > 0.4:
            return True
        return False

    def _extract_sections(self, text: str) -> list[dict]:
        """
        Find all section starts using the India Code pattern:
        "17. Time limit for payment of wages.—"
        Returns list of {section_number, section_title, page, text}
        """
        # Find all section start positions
        matches = list(INDIA_CODE_SECTION.finditer(text))

        if not matches:
            # Fallback: treat entire non-TOC text as one chunk
            page = self._find_page_at(text, 0)
            return [{'section_number': None, 'section_title': None,
                     'page': page, 'text': text}]

        sections = []
        for i, m in enumerate(matches):
            sec_num = m.group(1)
            sec_title = m.group(2).strip().rstrip('.')
            start = m.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            section_text = text[start:end].strip()
            page = self._find_page_at(text, start)
            sections.append({
                'section_number': sec_num,
                'section_title': sec_title,
                'page': page,
                'text': section_text,
            })

        return sections

    def _find_page_at(self, text: str, pos: int) -> Optional[int]:
        """Find the most recent [PAGE:N] marker before position."""
        last_page = 1
        for m in PAGE_MARKER.finditer(text):
            if m.start() > pos:
                break
            try:
                last_page = int(m.group(1))
            except ValueError:
                pass
        return last_page

    def _build_chunks(self, sections: list[dict]) -> list[LegalChunk]:
        chunks = []
        idx = 0
        for sec in sections:
            text = sec['text'].strip()
            # Remove page markers from chunk text
            clean_text = PAGE_MARKER.sub('', text).strip()
            # Strip boilerplate
            for pat in STRIP_PATTERNS:
                clean_text = pat.sub('', clean_text)
            clean_text = re.sub(r'\n{3,}', '\n\n', clean_text).strip()

            if not clean_text or len(clean_text) < self.MIN_CHUNK:
                continue

            if len(clean_text) <= self.MAX_CHUNK:
                chunks.append(self._make_chunk(clean_text, sec, idx))
                idx += 1
            else:
                sub_chunks = self._split_large(clean_text, sec)
                for sc in sub_chunks:
                    sc.chunk_index = idx
                    chunks.append(sc)
                    idx += 1

        return chunks

    def _make_chunk(self, text: str, sec: dict, idx: int = 0) -> LegalChunk:
        return LegalChunk(
            text=text,
            document_id=self.document_id,
            document_title=self.document_title,
            section_number=sec.get('section_number'),
            section_title=sec.get('section_title'),
            page=sec.get('page'),
            source_url=self.source_url,
            jurisdiction=self.jurisdiction,
            document_type=self.document_type,
            chunk_index=idx,
        )

    def _split_large(self, text: str, sec: dict) -> list[LegalChunk]:
        """Split oversized section at subsection boundaries (1), (2), (a)."""
        split_points = [0]
        for m in re.finditer(r'\n\s*\(\d+\)|\n\s*\([a-z]\)', text):
            split_points.append(m.start())
        split_points.append(len(text))

        chunks = []
        for i in range(len(split_points) - 1):
            segment = text[split_points[i]:split_points[i + 1]].strip()
            if len(segment) < self.MIN_CHUNK:
                if chunks:
                    # Merge with previous
                    prev = chunks[-1]
                    chunks[-1] = self._make_chunk(prev.text + '\n' + segment, sec)
                continue
            if len(segment) > self.MAX_CHUNK:
                # Hard split with overlap
                start = 0
                while start < len(segment):
                    end = min(start + self.MAX_CHUNK, len(segment))
                    if end < len(segment):
                        break_at = segment.rfind('. ', start, end)
                        if break_at > start:
                            end = break_at + 1
                    piece = segment[start:end].strip()
                    if piece:
                        chunks.append(self._make_chunk(piece, sec))
                    start = max(start + 1, end - self.OVERLAP)
            else:
                chunks.append(self._make_chunk(segment, sec))

        return chunks if chunks else [self._make_chunk(text[:self.MAX_CHUNK], sec)]