"""Rule-based extraction of report metadata and dynamically named structures."""

from __future__ import annotations

import re

_SPACE = re.compile(r"\s+")
_FIELD = re.compile(r"^([^:]{1,80}):\s*(.*)$")
_METADATA = (
    (
        "аппарат",
        re.compile(
            r"^(?:исследование\s+проводилось\s+на\s+)?аппарате?\s*:?\s*(.+)$",
            re.IGNORECASE,
        ),
    ),
    (
        "дата_исследования",
        re.compile(r"^дата\s+(?:выполнения|исследования)\s*:\s*(.+)$", re.I),
    ),
    (
        "дата_последней_менструации",
        re.compile(r"^дата\s+последней\s+менструации\s*:\s*(.+)$", re.I),
    ),
    (
        "дата_родов",
        re.compile(r"^дата\s+последних?\s+родов\s*:\s*(.+)$", re.I),
    ),
    (
        "тип_исследования",
        re.compile(r"^(?:тип\s+исследования|вид\s+исследования)\s*:\s*(.+)$", re.I),
    ),
)
_STUDY_TITLE = re.compile(
    r"\b(?:ультразвуков\w*|узи\b|уз-исследован\w*|"
    r"дуплексн\w*\s+сканирован\w*|эхографическ\w*\s+исследован\w*)",
    re.IGNORECASE,
)
_DESCRIPTION_HEADING = re.compile(r"^описание\s*:?\s*$", re.IGNORECASE)
_CONCLUSION_HEADING = re.compile(r"^заключение\s*:?\s*(.*)$", re.IGNORECASE)
_RECOMMENDATION_HEADING = re.compile(
    r"^(?:рекомендовано|рекомендована|рекомендованы|рекомендуется|"
    r"рекомендации)\b\s*:?\s*(.*)$",
    re.IGNORECASE,
)
_PROPERTY_PREFIX = re.compile(
    r"^(?P<label>"
    r"в\s+положении|положение|положен\w*|расположен\w*|расположение|"
    r"размеры|размер|объем|объём|контуры|форма|толщина(?:\s+\w+){0,3}|"
    r"длина|ширина|высота|эхоструктура(?:\s+\w+){0,3}|структура|"
    r"строма|фолликулярный\s+аппарат|фаллопиева\s+труба|"
    r"цервикальный\s+канал|эндоцервикс|базальный\s+контур|"
    r"линия\s+смыкания(?:\s+\w+){0,4}|кровоток|эхогенность|"
    r"состояние|просвет|стенки(?:\s+\w+){0,3}"
    r")\s+(?P<value>.+)$",
    re.IGNORECASE,
)
_FORMATION = re.compile(
    r"\b(?:образован\w*|кист\w*|узл\w*|миом\w*|полип\w*|"
    r"опухол\w*|аденом\w*|конкремент\w*|камн\w*)\b",
    re.IGNORECASE,
)
_NEGATED_FORMATION = re.compile(
    r"(?:не\s+(?:выявля\w*|определя\w*|визуализир\w*|лоцир\w*|обнаружива\w*)"
    r"|без\s+[^,.]*|отсутств\w*)",
    re.IGNORECASE,
)
_LATERALITY_PREFIX = re.compile(
    r"^(?:прав(?:ый|ая|ое|ые)|лев(?:ый|ая|ое|ые))\s+",
    re.IGNORECASE,
)
_KEYWORD_LABELS = {
    "в положении": "положение",
    "положение": "положение",
    "положен": "положение",
    "расположение": "расположение",
    "расположен": "расположение",
    "объем": "объем",
    "объём": "объем",
}


def _clean(value: str) -> str:
    return _SPACE.sub(" ", value).strip(" \t:;.")


def _key(value: str) -> str:
    normalized = _clean(value).casefold().replace("ё", "е")
    normalized = _LATERALITY_PREFIX.sub(
        lambda match: match.group(0).strip().casefold().replace(" ", "_") + "_",
        normalized,
    )
    normalized = re.sub(r"[^\w]+", "_", normalized, flags=re.UNICODE).strip("_")
    return _KEYWORD_LABELS.get(normalized, normalized) or "прочее"


def _add_value(target: dict[str, object], key: str, value: str) -> None:
    current = target.get(key)
    if current is None:
        target[key] = value
    elif isinstance(current, list):
        current.append(value)
    else:
        target[key] = [current, value]


def _is_section_heading(line: str) -> bool:
    clean = _clean(line).rstrip(":").strip()
    return (
        len(clean) <= 80
        and not re.search(r"[.!?,;]", clean)
        and clean == clean.upper()
        and any(character.isalpha() for character in clean)
    )


class ClinicalStructureParser:
    """Parse report sections without assuming a fixed list of organs."""

    def parse(self, text: str) -> dict[str, object]:
        structured, _ = self.parse_with_clinical_text(text)
        return structured

    def parse_with_clinical_text(
        self, text: str
    ) -> tuple[dict[str, object], str]:
        if not isinstance(text, str):
            raise TypeError("text должен быть строкой")

        result: dict[str, object] = {
            "служебная_информация": {},
            "структуры": {},
            "прочие_находки": [],
            "заключение": None,
            "рекомендации": None,
        }
        metadata = result["служебная_информация"]
        structures = result["структуры"]
        other_findings = result["прочие_находки"]
        assert isinstance(metadata, dict)
        assert isinstance(structures, dict)
        assert isinstance(other_findings, list)

        current_structure: dict[str, object] | None = None
        clinical_fragments: list[str] = []
        section = "preamble"
        for raw_line in text.splitlines():
            line = _clean(raw_line)
            if not line:
                continue
            if _DESCRIPTION_HEADING.fullmatch(line):
                section = "description"
                continue
            if _CONCLUSION_HEADING.match(line):
                match = _CONCLUSION_HEADING.match(line)
                assert match is not None
                section = "conclusion"
                current_structure = None
                value = _clean(match.group(1))
                if value:
                    self._append_section(result, "заключение", value)
                continue
            if _RECOMMENDATION_HEADING.match(line):
                match = _RECOMMENDATION_HEADING.match(line)
                assert match is not None
                section = "recommendations"
                current_structure = None
                value = _clean(match.group(1))
                if value:
                    self._append_section(result, "рекомендации", value)
                continue
            if section == "conclusion":
                self._append_section(result, "заключение", line)
                continue
            if section == "recommendations":
                self._append_section(result, "рекомендации", line)
                continue

            metadata_key = self._metadata_key(line)
            if metadata_key:
                _add_value(metadata, *metadata_key)
                continue

            if section == "description" and "тип_исследования" not in metadata:
                if _STUDY_TITLE.search(line):
                    metadata["тип_исследования"] = line
                    continue

            if section == "preamble":
                continue
            if _is_section_heading(line):
                structure_name = _key(line.rstrip(":"))
                current_structure = structures.setdefault(structure_name, {})
                assert isinstance(current_structure, dict)
                continue

            if current_structure is None:
                other_findings.append(line)
                clinical_fragments.append(line)
                continue

            clinical_fragment = self._parse_structure_line(current_structure, line)
            if clinical_fragment:
                clinical_fragments.append(clinical_fragment)

        return result, "\n".join(clinical_fragments)

    @staticmethod
    def _metadata_key(line: str) -> tuple[str, str] | None:
        for key, pattern in _METADATA:
            match = pattern.match(line)
            if match:
                return key, _clean(match.group(1))
        return None

    @staticmethod
    def _append_section(result: dict[str, object], key: str, value: str) -> None:
        current = result[key]
        result[key] = f"{current}\n{value}" if current else value

    def _parse_structure_line(
        self, structure: dict[str, object], line: str
    ) -> str | None:
        field = _FIELD.match(line)
        if field and len(field.group(1).split()) <= 6:
            label = _key(field.group(1))
            value = _clean(field.group(2))
            if value:
                _add_value(structure, label, value)
                if self._is_positive_formation(value):
                    self._append_list(structure, "образования", value)
                    return value
                return None

        property_match = _PROPERTY_PREFIX.match(line)
        if property_match:
            label = _key(property_match.group("label"))
            value = _clean(property_match.group("value"))
            _add_value(structure, label, value)
            return None

        if self._is_positive_formation(line):
            self._append_list(structure, "образования", line)
            return line

        self._append_list(structure, "наблюдения", line)
        return line

    @staticmethod
    def _is_positive_formation(text: str) -> bool:
        return bool(_FORMATION.search(text)) and not bool(_NEGATED_FORMATION.search(text))

    @staticmethod
    def _append_list(target: dict[str, object], key: str, value: str) -> None:
        current = target.setdefault(key, [])
        assert isinstance(current, list)
        current.append(value)
