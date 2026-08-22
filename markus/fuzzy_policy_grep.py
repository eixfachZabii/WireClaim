from __future__ import annotations

import json
import re
import time
from pathlib import Path


def fuzzy_section_search(
    text: str,
    query: str,
    max_distance: int = 2,
    top_k: int = 3,
) -> list[dict[str, object]]:
    if not query:
        raise ValueError("query must not be empty")
    if max_distance < 0 or top_k < 1:
        raise ValueError("max_distance must be >= 0 and top_k must be >= 1")

    lines = text.splitlines()
    headers: list[tuple[int, str] | None] = []
    for line in lines:
        stripped = line.strip()
        if re.match(r"^PART\s+\d+\b", stripped, re.IGNORECASE):
            headers.append((0, stripped))
        elif match := re.match(r"^(\d+(?:\.\d+)*)(?:[.)])?\s+\S", stripped):
            headers.append((len(match.group(1).split(".")), stripped))
        elif stripped.isupper() and any(character.isalpha() for character in stripped):
            headers.append((1, stripped))
        else:
            headers.append(None)

    paragraphs: list[tuple[int, int]] = []
    for line_index in range(len(lines)):
        section_start = line_index
        while (
            section_start > 0
            and lines[section_start - 1].strip()
            and headers[section_start - 1] is None
        ):
            section_start -= 1
        section_end = line_index + 1
        while (
            section_end < len(lines)
            and lines[section_end].strip()
            and headers[section_end] is None
        ):
            section_end += 1
        paragraphs.append((section_start, section_end))

    normalized_query = query.casefold()
    matches: dict[tuple[int, int], tuple[int, int]] = {}
    for line_index, line in enumerate(lines):
        previous = list(range(len(normalized_query) + 1))
        distance = len(normalized_query)
        for character in line.casefold():
            current = [0]
            for query_index, query_character in enumerate(normalized_query, start=1):
                current.append(
                    min(
                        previous[query_index] + 1,
                        current[query_index - 1] + 1,
                        previous[query_index - 1] + (query_character != character),
                    )
                )
            distance = min(distance, current[-1])
            if distance == 0:
                break
            previous = current

        section = paragraphs[line_index]
        if distance <= max_distance and (
            section not in matches or (distance, line_index) < matches[section]
        ):
            matches[section] = (distance, line_index)

    results: list[dict[str, object]] = []
    ranked_matches = sorted(
        ((distance, line_index, section_start, section_end) for (section_start, section_end), (distance, line_index) in matches.items()),
        key=lambda match: (match[0], match[1]),
    )
    for distance, line_index, section_start, section_end in ranked_matches[:top_k]:
        header_index = section_start
        while header_index > 0 and headers[header_index] is None:
            header_index -= 1

        hierarchy: dict[int, str] = {}
        for header in headers[: header_index + 1]:
            if header is None:
                continue
            level, title = header
            for existing_level in tuple(hierarchy):
                if existing_level >= level:
                    del hierarchy[existing_level]
            hierarchy[level] = title

        results.append(
            {
                "line_index": line_index,
                "distance": distance,
                "match": lines[line_index],
                "header_path": [
                    {"level": level, "header": hierarchy[level]}
                    for level in sorted(hierarchy)
                ],
                "section": {
                    "start_line_index": section_start,
                    "end_line_index": section_end - 1,
                    "text": "\n".join(lines[section_start:section_end]),
                },
            }
        )
    return results


if __name__ == "__main__":
    POLICY_PATH = Path(
        r"C:\Users\marku\Desktop\WireClaim\[PUBLIC] EHL Cases\cases\case_08\policy.txt"
    )
    QUERIES = ["rug cleaning", "billiard table"]
    MAX_DISTANCE = 2
    TOP_K = 3

    policy_text = POLICY_PATH.read_text(encoding="utf-8")
    for query in QUERIES:
        started_at = time.perf_counter()
        results = fuzzy_section_search(policy_text, query, MAX_DISTANCE, TOP_K)
        duration_ms = (time.perf_counter() - started_at) * 1000
        print(
            json.dumps(
                {
                    "query": query,
                    "runtime_ms": round(duration_ms, 3),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
