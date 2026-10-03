"""Rule-based extraction of report metadata and dynamically named structures."""

from __future__ import annotations

import re

from yargy import Parser
from yargy.pipelines import morph_pipeline

_SPACE = re.compile(r"\s+")
_FIELD = re.compile(r"^([^:]{1,80}):\s*(.*)$")
_SIDE_HEADING = re.compile(r"^(справа|слева)\s*:\s*$", re.IGNORECASE)
_VESSEL_MEASUREMENT = re.compile(
    r"^\s*(?P<metric>Vps|Vpd|Vmean|RI|PI)\s*[–—-]?\s*"
    r"(?P<value>\d+(?:[.,]\d+)?)\s*"
    r"(?P<unit>см\s*/\s*сек|см\s*/\s*с|м\s*/\s*с)?"
    r"(?P<reference>.*)$",
    re.IGNORECASE,
)
_METADATA = (
    (
        "аппарат",
        re.compile(
            r"^(?:исследование\s+(?:проводилось|выполнено)\s+на\s+)?"
            r"аппарате?\s*:?\s*(.+)$",
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
    r"(?:^\s*(?:исследован\w*|протокол)\b|"
    r"\b(?:ультразвуков\w*|узи\b|уздг\b|уздс\b|уз-исследован\w*|"
    r"допплер\w*|дуплексн\w*\s+(?:сканирован\w*|исследован\w*)|"
    r"сканирован\w*|эхографическ\w*\s+исследован\w*))",
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
    "в_положении": "положение",
    "положение": "положение",
    "расположение": "расположение",
    "расположен": "расположение",
    "объем": "объем",
}
_FIELD_LABELS = {
    "размер",
    "размеры",
    "объем",
    "контуры",
    "положение",
    "расположение",
    "толщина",
    "длина",
    "ширина",
    "высота",
    "эхоструктура",
    "структура",
    "строма",
    "фолликулярный аппарат",
    "фаллопиева труба",
    "цервикальный канал",
    "эндоцервикс",
    "базальный контур",
    "кровоток",
    "эхогенность",
    "состояние",
    "просвет",
    "стенки",
}
_SERVICE_LABELS = {
    "оборудование": "оборудование",
    "модель аппарата": "аппарат",
    "датчик": "датчик",
    "уз датчик": "датчик",
    "врач": "врач",
    "пол": "пол",
    "пациент": "пациент",
    "пациентка": "пациент",
    "дата рождения": "дата_рождения",
    "номер карты": "номер_карты",
    "частота": "частота",
}
_VESSEL_NAMES = {
    "оба": "ОБА",
    "пба": "ПБА",
    "гба": "ГБА",
    "пка": "ПкА",
    "збба": "ЗББА",
    "пбба": "ПББА",
    "тас": "ТАС",
    "опа": "ОПА",
    "нпа": "НПА",
}
_VESSEL_PARSER = Parser(
    morph_pipeline(list(_VESSEL_NAMES.keys()))
)


def _clean(value: str) -> str:
    return _SPACE.sub(" ", value).strip(" \t;.")


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
    all_caps_heading = (
        len(clean) <= 80
        and not re.search(r"[.!?,;]", clean)
        and clean == clean.upper()
        and any(character.isalpha() for character in clean)
    )
    colon_heading = line.rstrip().endswith(":") and _key(clean) not in _FIELD_LABELS
    return all_caps_heading or colon_heading


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
            "стороны": {},
            "прочие_находки": [],
            "заключение": None,
            "рекомендации": None,
        }
        metadata = result["служебная_информация"]
        structures = result["структуры"]
        sides = result["стороны"]
        other_findings = result["прочие_находки"]
        assert isinstance(metadata, dict)
        assert isinstance(structures, dict)
        assert isinstance(sides, dict)
        assert isinstance(other_findings, list)

        has_description_heading = any(
            _DESCRIPTION_HEADING.fullmatch(_clean(line))
            for line in text.splitlines()
        )
        current_structure: dict[str, object] | None = None
        current_side: dict[str, object] | None = None
        clinical_fragments: list[str] = []
        section = "preamble" if has_description_heading else "description"
        for raw_line in text.splitlines():
            line = _clean(raw_line)
            if not line:
                if section == "description" and current_side is None:
                    current_structure = None
                continue
            if _DESCRIPTION_HEADING.fullmatch(line):
                section = "description"
                continue
            if _CONCLUSION_HEADING.match(line):
                match = _CONCLUSION_HEADING.match(line)
                assert match is not None
                section = "conclusion"
                current_structure = None
                current_side = None
                value = _clean(match.group(1))
                if value:
                    self._append_section(result, "заключение", value)
                continue
            if _RECOMMENDATION_HEADING.match(line):
                match = _RECOMMENDATION_HEADING.match(line)
                assert match is not None
                section = "recommendations"
                current_structure = None
                current_side = None
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

            if "тип_исследования" not in metadata:
                if _STUDY_TITLE.search(line):
                    metadata["тип_исследования"] = line
                    continue

            if section == "preamble":
                generic_metadata = self._generic_metadata(line)
                if generic_metadata:
                    _add_value(metadata, *generic_metadata)
                continue
            side_heading = _SIDE_HEADING.fullmatch(line)
            if side_heading:
                side_name = side_heading.group(1).casefold()
                current_side = sides.setdefault(side_name, {})
                assert isinstance(current_side, dict)
                current_structure = None
                continue

            if current_side is not None:
                vessel_line = self._parse_vessel_measurement(current_side, line)
                if vessel_line is not None:
                    clinical_fragments.append(vessel_line)
                else:
                    self._append_list(current_side, "наблюдения", line)
                    clinical_fragments.append(line)
                continue

            if _is_section_heading(line):
                structure_name = _key(line.rstrip(":"))
                current_structure = structures.setdefault(structure_name, {})
                assert isinstance(current_structure, dict)
                continue

            if section != "preamble" and current_structure is None:
                generic_metadata = self._generic_metadata(line)
                if generic_metadata:
                    _add_value(metadata, *generic_metadata)
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
    def _generic_metadata(line: str) -> tuple[str, str] | None:
        field = _FIELD.match(line)
        if not field or len(field.group(1).split()) > 6:
            return None
        label = _clean(field.group(1)).casefold().replace("ё", "е")
        output_key = _SERVICE_LABELS.get(label)
        if not output_key:
            return None
        value = _clean(field.group(2))
        return (output_key, value) if value else None

    @staticmethod
    def _append_section(result: dict[str, object], key: str, value: str) -> None:
        current = result[key]
        result[key] = f"{current}\n{value}" if current else value

    def _parse_structure_line(
        self, structure: dict[str, object], line: str
    ) -> str | None:
        field = _FIELD.match(line)
        if (
            field
            and len(field.group(1).split()) <= 6
            and not re.search(r"[.!?]", field.group(1))
        ):
            label = _key(field.group(1))
            value = _clean(field.group(2))
            if value:
                if label == "образование":
                    self._append_list(structure, "образования", value)
                    return value
                else:
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
    def _parse_vessel_measurement(
        side: dict[str, object], line: str
    ) -> str | None:
        abbreviations = list(_VESSEL_PARSER.findall(line))
        if len(abbreviations) != 1:
            return None
        start, end = abbreviations[0].span
        abbreviation = _key(line[start:end])
        vessel_name = _VESSEL_NAMES.get(abbreviation)
        if vessel_name is None:
            return None
        metric = _VESSEL_MEASUREMENT.match(line[end:])
        if not metric:
            return None

        vessels = side.setdefault("сосуды", {})
        assert isinstance(vessels, dict)
        vessel = vessels.setdefault(vessel_name, {})
        assert isinstance(vessel, dict)
        measurements = vessel.setdefault("измерения", {})
        assert isinstance(measurements, dict)

        value: dict[str, str] = {
            "значение": _clean(f"{metric.group('value')} {metric.group('unit') or ''}")
        }
        reference = _clean(metric.group("reference"))
        if reference:
            value["референс"] = reference.strip("()")
        _add_value(measurements, metric.group("metric"), value)
        return line

    @staticmethod
    def _is_positive_formation(text: str) -> bool:
        return bool(_FORMATION.search(text)) and not bool(_NEGATED_FORMATION.search(text))

    @staticmethod
    def _append_list(target: dict[str, object], key: str, value: str) -> None:
        current = target.setdefault(key, [])
        assert isinstance(current, list)
        current.append(value)
