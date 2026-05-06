"""Project indexing and semantic retrieval for smart context selection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .schemas import WorkspaceFile


STOPWORDS = {
    "and",
    "are",
    "but",
    "class",
    "const",
    "def",
    "export",
    "false",
    "from",
    "function",
    "import",
    "none",
    "null",
    "return",
    "self",
    "test",
    "that",
    "the",
    "this",
    "true",
    "type",
    "var",
}


@dataclass
class FileIndex:
    """Index entry for a project file."""

    path: str
    kind: str
    size: int
    extension: str
    keywords: list[str]
    is_large: bool = False
    estimated_lines: int = 0
    sample_strategy: str = ""
    relevance_score: float = 0.0


class ProjectIndexer:
    """Indexes project files for intelligent context retrieval."""

    FILE_CATEGORIES = {
        "config": [".json", ".yaml", ".yml", ".toml", ".ini", ".env"],
        "code": [".py", ".ts", ".tsx", ".js", ".jsx", ".cpp", ".c", ".h", ".go", ".rs", ".java"],
        "markup": [".md", ".html", ".xml", ".htm"],
        "script": [".sh", ".bat", ".ps1", ".bash", ".cmd"],
        "style": [".css", ".scss", ".sass", ".less"],
        "data": [".json", ".csv", ".sql", ".db"],
        "other": [],
    }

    def __init__(self):
        self.index: dict[str, FileIndex] = {}

    def build_from_workspace(
        self,
        root: Path,
        files: list[WorkspaceFile],
        *,
        max_content_chars: int = 4000,
    ) -> None:
        """Build an index from scanned workspace files."""

        self.index.clear()

        for file in files:
            if file.kind != "text":
                continue

            content: str | None = None
            target = root / file.path
            try:
                if file.size > 160_000:
                    content = self._sample_text_file(target, max_content_chars=max_content_chars)
                else:
                    content = target.read_text(encoding="utf-8", errors="replace")[:max_content_chars]
            except OSError:
                content = None

            self.index_file(
                file.path,
                file.kind,
                file.size,
                content=content,
                is_large=bool(file.is_large or file.size >= 1_000_000),
                estimated_lines=int(file.estimated_lines or 0),
                sample_strategy=file.large_file_strategy,
            )

    def index_file(
        self,
        path: str,
        kind: str,
        size: int,
        *,
        content: str | None = None,
        is_large: bool = False,
        estimated_lines: int = 0,
        sample_strategy: str = "",
    ) -> FileIndex:
        """Add a file to the index."""

        ext = Path(path).suffix.lower()
        keywords = self._extract_keywords(path, content)

        entry = FileIndex(
            path=path,
            kind=kind,
            size=size,
            extension=ext,
            keywords=keywords,
            is_large=is_large,
            estimated_lines=estimated_lines,
            sample_strategy=sample_strategy,
        )

        self.index[path] = entry
        return entry

    def find_relevant_files(self, query: str, max_results: int = 10) -> list[FileIndex]:
        """Find files relevant to a query."""

        query_terms = self._tokenize(query)
        if not query_terms:
            query_terms = ["workspace"]

        results: list[FileIndex] = []
        query_text = query.lower()

        for entry in self.index.values():
            score = 0.0
            keyword_set = set(entry.keywords)
            path_text = entry.path.lower()
            stem = Path(entry.path).stem.lower()

            for term in query_terms:
                if term in keyword_set:
                    score += 2.2
                elif any(term in keyword for keyword in keyword_set):
                    score += 0.8

                if term == stem:
                    score += 2.8
                elif term in path_text:
                    score += 1.6

            if any(term in {"config", "settings", "setup", "env"} for term in query_terms):
                if entry.extension in self.FILE_CATEGORIES["config"]:
                    score += 2.4

            if any(term in {"test", "tests", "spec", "failing"} for term in query_terms):
                if any(marker in path_text for marker in ("test", "spec")):
                    score += 2.0

            if any(term in {"ui", "frontend", "react", "component"} for term in query_terms):
                if entry.extension in {".tsx", ".jsx", ".css"}:
                    score += 1.8

            if any(term in {"api", "backend", "fastapi", "server"} for term in query_terms):
                if entry.extension in {".py", ".go", ".rs", ".ts"}:
                    score += 1.6

            if "readme" in query_text and Path(entry.path).name.lower() == "readme.md":
                score += 3.0

            if entry.is_large and any(term in {"large", "huge", "monolith", "single", "lines", "slice", "chunk"} for term in query_terms):
                score += 2.2
            if entry.estimated_lines >= 100_000 and any(term in {"500000", "500k", "line", "lines"} for term in query_terms):
                score += 2.5

            entry.relevance_score = score
            if score > 0:
                results.append(entry)

        results.sort(key=lambda item: (-item.relevance_score, item.path))
        return results[:max_results]

    def get_files_by_type(self, file_type: str) -> list[FileIndex]:
        """Get all files of a specific type."""

        extensions = self.FILE_CATEGORIES.get(file_type, [])
        return [entry for entry in self.index.values() if entry.extension in extensions]

    def _extract_keywords(self, path: str, content: str | None = None) -> list[str]:
        parts = [part.lower() for part in Path(path).parts if part not in {".", ".."}]
        stem = Path(path).stem.lower()
        keywords = set(parts + [stem])
        keywords.update(self._tokenize(path.replace("\\", "/").replace(".", " ")))

        if content:
            keywords.update(self._extract_content_keywords(content))

        return sorted(keyword for keyword in keywords if keyword and keyword not in STOPWORDS)

    def _extract_content_keywords(self, content: str) -> set[str]:
        tokens = self._tokenize(content)
        if not tokens:
            return set()

        weighted: list[str] = []
        for token in tokens[:400]:
            weighted.append(token)

        return set(weighted[:120])

    def _sample_text_file(self, path: Path, *, max_content_chars: int) -> str:
        try:
            size = path.stat().st_size
        except OSError:
            return ""
        if size <= 0:
            return ""

        byte_budget = max(1024, min(size, max_content_chars * 2))
        head_budget = max(512, byte_budget // 2)
        tail_budget = max(512, byte_budget - head_budget)
        try:
            with path.open("rb") as handle:
                head = handle.read(head_budget)
                tail = b""
                if size > head_budget:
                    handle.seek(max(0, size - tail_budget))
                    tail = handle.read(tail_budget)
        except OSError:
            return ""

        if not tail:
            return head.decode("utf-8", errors="replace")[:max_content_chars]
        head_text = head.decode("utf-8", errors="replace")
        tail_text = tail.decode("utf-8", errors="replace")
        return f"{head_text[: max_content_chars // 2]}\n{tail_text[-max_content_chars // 2 :]}"

    def _tokenize(self, text: str) -> list[str]:
        return [
            token.lower()
            for token in re.findall(r"[A-Za-z_][A-Za-z0-9_\-]{2,}", text)
            if token and token.lower() not in STOPWORDS
        ]
