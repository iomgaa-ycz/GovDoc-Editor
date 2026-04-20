"""TenderDocParser.

设计基线：`docs/design.md` §6 / `docs/TD.md` T0.10。
"""

from __future__ import annotations

import re
from typing import Iterable

from pydantic import Field

from govdoc.schemas.common import GovDocModel


SECTION_ALIASES: dict[str, tuple[str, ...]] = {
    "资格要求": ("资格要求", "资格条件", "资格审查"),
    "评分办法": ("评分办法", "评标办法", "评审办法"),
    "合同条款": ("合同条款", "合同主要条款", "合同专用条款"),
}


class TenderSection(GovDocModel):
    name: str
    char_start: int
    char_end: int
    text: str


class TenderStructure(GovDocModel):
    sections: list[TenderSection] = Field(default_factory=list)


def _iter_matches(md: str) -> Iterable[tuple[str, int]]:
    for canonical_name, aliases in SECTION_ALIASES.items():
        for alias in aliases:
            pattern = re.compile(rf"^(?:#+\s*)?{re.escape(alias)}\s*$", re.MULTILINE)
            match = pattern.search(md)
            if match:
                yield canonical_name, match.start()
                break


def parse(md: str) -> TenderStructure:
    normalized = md.replace("\r\n", "\n")
    matches = sorted(_iter_matches(normalized), key=lambda item: item[1])
    if not matches:
        return TenderStructure(
            sections=[
                TenderSection(
                    name="全文",
                    char_start=0,
                    char_end=len(normalized),
                    text=normalized,
                )
            ]
        )

    sections: list[TenderSection] = []
    for index, (name, start) in enumerate(matches):
        end = matches[index + 1][1] if index + 1 < len(matches) else len(normalized)
        sections.append(
            TenderSection(
                name=name,
                char_start=start,
                char_end=end,
                text=normalized[start:end].strip(),
            )
        )
    return TenderStructure(sections=sections)


def locate_section(md: str, section: str) -> TenderSection | None:
    structure = parse(md)
    normalized_query = section.strip()
    for item in structure.sections:
        if item.name == normalized_query:
            return item
    return None
