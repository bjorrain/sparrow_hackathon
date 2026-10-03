#!/usr/bin/env python3
"""Extract the «Описание» and «Заключение» sections from DOCX files."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import TextIO
from xml.etree import ElementTree
from zipfile import BadZipFile, ZipFile

WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
HEADING_RE = re.compile(
    r"^\s*(Описание|Заключение|Диагноз|Рекомендации)"
    r"(?:\s*:\s*|\s*$)",
    re.IGNORECASE,
)


def read_docx_paragraphs(path: Path) -> list[str]:
    """Read paragraphs from the main document body, including table cells."""
    with ZipFile(path) as docx:
        document = ElementTree.fromstring(docx.read("word/document.xml"))

    paragraphs = []
    for paragraph in document.iter(f"{WORD_NS}p"):
        parts = []
        for node in paragraph.iter():
            if node.tag == f"{WORD_NS}t":
                parts.append(node.text or "")
            elif node.tag == f"{WORD_NS}tab":
                parts.append("\t")
            elif node.tag in (f"{WORD_NS}br", f"{WORD_NS}cr"):
                parts.append("\n")
        text = "".join(parts).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def extract_sections(paragraphs: list[str]) -> dict[str, str | None]:
    """Extract section text until the next recognized section heading."""
    extracted: dict[str, list[str]] = {
        "description": [],
        "conclusion": [],
    }
    active_section: str | None = None

    for paragraph in paragraphs:
        heading = HEADING_RE.match(paragraph)
        if heading:
            label = heading.group(1).casefold()
            if label in ("описание", "заключение"):
                active_section = (
                    "description" if label == "описание" else "conclusion"
                )
                inline_text = paragraph[heading.end() :].strip()
                if inline_text:
                    extracted[active_section].append(inline_text)
            else:
                active_section = None
            continue

        if active_section:
            extracted[active_section].append(paragraph)

    return {
        name: "\n".join(lines).strip() or None
        for name, lines in extracted.items()
    }


def find_docx_files(source: Path) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() != ".docx":
            raise ValueError(f"Ожидался файл .docx: {source}")
        return [source]
    if source.is_dir():
        return sorted(path for path in source.rglob("*.docx") if path.is_file())
    raise FileNotFoundError(f"Путь не найден: {source}")


def write_results(records: list[dict[str, str | None]], output: TextIO) -> None:
    json.dump(records, output, ensure_ascii=False, indent=2)
    output.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Извлечь разделы «Описание» и «Заключение» из файлов DOCX."
    )
    parser.add_argument(
        "source",
        nargs="?",
        type=Path,
        default=Path("условия"),
        help="DOCX-файл или папка с DOCX-файлами (по умолчанию: условия)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="файл для сохранения JSON (по умолчанию выводится в stdout)",
    )
    args = parser.parse_args()

    try:
        files = find_docx_files(args.source)
    except (FileNotFoundError, ValueError) as error:
        parser.error(str(error))

    records = []
    failed = False
    for path in files:
        try:
            sections = extract_sections(read_docx_paragraphs(path))
            records.append(
                {
                    "file": path.as_posix(),
                    **sections,
                }
            )
        except (BadZipFile, KeyError, ElementTree.ParseError, OSError) as error:
            print(f"Не удалось обработать {path}: {error}", file=sys.stderr)
            failed = True

    try:
        if args.output:
            with args.output.open("w", encoding="utf-8") as output:
                write_results(records, output)
        else:
            write_results(records, sys.stdout)
    except OSError as error:
        print(f"Не удалось записать результат: {error}", file=sys.stderr)
        return 1

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
