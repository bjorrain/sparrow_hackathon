"""Rule-based extraction of report metadata and dynamically named structures."""

from __future__ import annotations

import re

from yargy import Parser
from yargy.pipelines import morph_pipeline

_SPACE = re.compile(r"\s+")
_FIELD = re.compile(r"^([^:–—-]{1,80}?)\s*(?::|[–—-])\s*(.*)$")
_PROSTATE_ANCHOR = re.compile(
    r"\b(?:предстательн\w*\s+желез\w*|простатическ\w*\s+желез\w*)\b",
    re.IGNORECASE,
)
_PROSTATE_TITLE = re.compile(
    r"^\s*предстательн\w*\s+желез\w*\s*[,—-]\s*(.+?)\s*$",
    re.IGNORECASE,
)
_PROSTATE_ENTITY_LINES = (
    (
        re.compile(r"^простатическая\s+часть\s+уретры\s*[–—-]\s*(.*)$", re.I),
        "простатическая_часть_уретры",
    ),
    (
        re.compile(r"^уретральный\s+канал\s+и\s+шейка\s+мочевого\s+пузыря\s*(.*)$", re.I),
        "уретральный_канал_и_шейка_мочевого_пузыря",
    ),
    (
        re.compile(r"^семенные\s+пузырьки\s*:\s*(.*)$", re.I),
        "семенные_пузырьки",
    ),
    (
        re.compile(r"^перипростатические\s+вены\s*(.*)$", re.I),
        "перипростатические_вены",
    ),
)
_SIDE_HEADING = re.compile(r"^(справа|слева)\s*:\s*$", re.IGNORECASE)
_TECHNICAL_HEADER = re.compile(
    r"^(ультразвуковая\s+диагностическая\s+система)\s*:?\s*$",
    re.IGNORECASE,
)
_INLINE_DIMENSIONS = re.compile(
    r"^(?P<label>длинник|поперечник|квр|вр|площадь|головка|тело|хвост)"
    r"\s*:?\s*(?P<value>\d[\d.,]*\s*(?:кв\.?\s*см|мм|см(?:2|²|3|³)?|мл|м))"
    r"(?:\s*,\s*(?P<second_label>длинник|поперечник|квр|вр|площадь|"
    r"головка|тело|хвост)\s*:?\s*"
    r"(?P<second_value>\d[\d.,]*\s*(?:кв\.?\s*см|мм|см(?:2|²|3|³)?|мл|м)))?$",
    re.IGNORECASE,
)
_DASHED_PROPERTY = re.compile(
    r"^(?P<label>.+?)\s*[-–—]\s*(?P<property>толщина|диаметр)\s*:\s*"
    r"(?P<value>.+)$",
    re.IGNORECASE,
)
_INDEPENDENT_FINDING = re.compile(
    r"^(?:в\s+(?:позадиматочном|дугласовом)\s+пространстве|"
    r"свободная\s+жидкость)\b",
    re.IGNORECASE,
)
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
    "форма",
    "структура",
    "эхогенность предстательной железы",
    "при цдк",
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
    return _SPACE.sub(" ", value).strip(" \t.,;:–—-")


def _key(value: str) -> str:
    normalized = _clean(value).casefold().replace("ё", "е")
    normalized = _LATERALITY_PREFIX.sub(
        lambda match: match.group(0).strip().casefold().replace(" ", "_") + "_",
        normalized,
    )
    normalized = re.sub(r"[^\w]+", "_", normalized, flags=re.UNICODE).strip("_")
    return _KEYWORD_LABELS.get(normalized, normalized) or "прочее"


def _add_value(target: dict[str, object], key: str, value: object) -> None:
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
    empty_colon_heading = bool(re.fullmatch(r"\s*[^:]{1,80}:\s*", line))
    return all_caps_heading or empty_colon_heading


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
        inferred_primary = (
            "предстательная_железа"
            if _PROSTATE_ANCHOR.search(text)
            else None
        )
        current_structure: dict[str, object] | None = None
        pending_property: str | None = None
        current_side: dict[str, object] | None = None
        pending_technical_header = False
        clinical_fragments: list[str] = []
        section = "preamble" if has_description_heading else "description"
        for raw_line in text.splitlines():
            if re.fullmatch(r"\s*структура\s*:\s*", raw_line, re.IGNORECASE):
                if current_structure is not None:
                    current_structure.setdefault("структура", [])
                    pending_property = "структура"
                continue
            line = _clean(raw_line)
            if not line:
                continue
            prostate_title = _PROSTATE_TITLE.match(line)
            if prostate_title:
                metadata["тип_исследования"] = _clean(prostate_title.group(1))
                if inferred_primary:
                    current_structure = structures.setdefault(inferred_primary, {})
                continue
            if _DESCRIPTION_HEADING.fullmatch(line):
                section = "description"
                if inferred_primary:
                    current_structure = structures.setdefault(inferred_primary, {})
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
            technical_header = _TECHNICAL_HEADER.fullmatch(line)
            if technical_header:
                metadata["тип_оборудования"] = _clean(technical_header.group(1))
                pending_technical_header = True
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

            if pending_technical_header and current_structure is None:
                metadata["оборудование"] = line
                pending_technical_header = False
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
            side_heading = _SIDE_HEADING.fullmatch(raw_line.strip())
            if side_heading:
                side_name = side_heading.group(1).casefold()
                current_side = sides.setdefault(side_name, {})
                assert isinstance(current_side, dict)
                current_structure = None
                pending_property = None
                continue

            if _is_section_heading(raw_line):
                structure_name = _key(line.rstrip(":"))
                current_structure = structures.setdefault(structure_name, {})
                assert isinstance(current_structure, dict)
                continue

            if current_side is not None:
                vessel_line = self._parse_vessel_measurement(current_side, line)
                if vessel_line is not None:
                    clinical_fragments.append(vessel_line)
                else:
                    self._append_list(current_side, "наблюдения", line)
                    clinical_fragments.append(line)
                continue

            if _INDEPENDENT_FINDING.match(line):
                other_findings.append(line)
                clinical_fragments.append(line)
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

            if self._is_empty_label(line, "структура"):
                current_structure.setdefault("структура", [])
                pending_property = "структура"
                continue
            if pending_property and not self._starts_new_structure_field(line):
                self._append_list(
                    current_structure,
                    pending_property,
                    line.lstrip("-• ").rstrip(";"),
                )
                clinical_fragments.append(line.lstrip("-• ").rstrip(";"))
                continue
            pending_property = None

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
        dashed_property = _DASHED_PROPERTY.fullmatch(line)
        if dashed_property:
            key = _key(f"{dashed_property.group('label')}_{dashed_property.group('property')}")
            _add_value(structure, key, _clean(dashed_property.group("value")))
            return None

        dimensions = _INLINE_DIMENSIONS.fullmatch(line)
        if dimensions:
            _add_value(
                structure,
                _key(dimensions.group("label")),
                _clean(dimensions.group("value")),
            )
            if dimensions.group("second_label"):
                _add_value(
                    structure,
                    _key(dimensions.group("second_label")),
                    _clean(dimensions.group("second_value")),
                )
            return None

        parts = self._split_labeled_clauses(line)
        if len(parts) > 1:
            findings = [
                finding
                for part in parts
                if (finding := self._parse_structure_line(structure, part.strip()))
            ]
            return "\n".join(findings) or None

        inline_measurement = re.match(
            r"^(?P<label>.+?)\s*:\s*(?P<value>.+?),\s*"
            r"(?P<secondary>толщина|диаметр|длинник|поперечник)\s+"
            r"(?P<secondary_value>\d[\d.,]*\s*(?:мм|см|мл))$",
            line,
            re.IGNORECASE,
        )
        if inline_measurement:
            label = _key(inline_measurement.group("label"))
            first_value = _clean(inline_measurement.group("value"))
            _add_value(structure, label, first_value)
            _add_value(
                structure,
                _key(f"{label}_{inline_measurement.group('secondary')}"),
                _clean(inline_measurement.group("secondary_value")),
            )
            return None

        for pattern, structure_name in _PROSTATE_ENTITY_LINES:
            match = pattern.match(line)
            if match:
                nested = structure.setdefault(structure_name, {})
                assert isinstance(nested, dict)
                remainder = _clean(match.group(1))
                if remainder:
                    findings = self._record_entity_text(nested, remainder)
                    return "\n".join(findings) or None
                return None

        field = _FIELD.match(line)
        if field and len(field.group(1).split()) <= 6:
            raw_label = _clean(field.group(1))
            label = _key(raw_label)
            value = _clean(field.group(2))
            thickness_suffix = re.fullmatch(
                r"(?P<parent>.+?)\s*[-–—]\s*толщина", raw_label, re.I
            )
            if thickness_suffix:
                label = _key(f"{thickness_suffix.group('parent')}_толщина")
            if _clean(field.group(1)).casefold().startswith("при исследовании "):
                self._append_list(structure, "наблюдения", line)
                return line
            if label == "эхогенность_предстательной_железы":
                label = "эхогенность"
            if label == "при_цдк":
                label = "васкуляризация"
            if label in {"семенные_пузырьки", "семенной_пузырек"}:
                nested = structure.setdefault("семенные_пузырьки", {})
                assert isinstance(nested, dict)
                self._record_entity_text(nested, value)
                return value
            if label in {"уретральный_канал_и_шейка_мочевого_пузыря"}:
                nested = structure.setdefault(
                    "уретральный_канал_и_шейка_мочевого_пузыря", {}
                )
                assert isinstance(nested, dict)
                self._record_entity_text(nested, value)
                return value
            if value:
                if label == "структура":
                    if self._is_positive_formation(value):
                        self._append_list(structure, "образования", value)
                        return value
                    self._append_list(structure, label, value)
                    return value
                if label == "образование":
                    self._append_list(structure, "образования", value)
                    return value
                if label == "образования" and self._is_positive_formation(value):
                    self._append_list(structure, "образования", value)
                    return value
                if label == "объем":
                    value = self._parse_measurement_value(value)
                    structure[label] = value
                    return None
                if label == "эхогенность_предстательной_железы":
                    label = "эхогенность"
                _add_value(structure, label, value)
                if self._is_positive_formation(value):
                    self._append_list(structure, "образования", value)
                    return value
                if label == "васкуляризация" or self._is_clinical_statement(value):
                    return value
                return None
            if label == "структура":
                structure.setdefault(label, [])
            return None

        property_match = _PROPERTY_PREFIX.match(line)
        if property_match:
            label = _key(property_match.group("label"))
            value = _clean(property_match.group("value"))
            if label == "объем":
                value = self._parse_measurement_value(value)
            _add_value(structure, label, value)
            return None

        measurement = re.match(
            r"^(размеры|размер|объем|объём)\s+(.+)$",
            line,
            re.IGNORECASE,
        )
        if measurement:
            label = _key(measurement.group(1))
            value = _clean(measurement.group(2))
            if label == "объем":
                value = self._parse_measurement_value(value)
            _add_value(structure, label, value)
            return None

        if self._is_zone_description(line):
            self._append_list(structure, "структура", line.lstrip("-• ").strip())
            return line.lstrip("-• ").strip()

        if self._is_positive_formation(line):
            self._append_list(structure, "образования", line)
            return line

        self._append_list(structure, "наблюдения", line)
        return line if self._is_clinical_statement(line) else None

    @staticmethod
    def _is_zone_description(line: str) -> bool:
        return bool(re.match(r"^[-•]?\s*в\s+.+?\s+зонах?\s*[–—-]", line, re.I))

    def _record_entity_text(
        self, entity: dict[str, object], text: str
    ) -> list[str]:
        clinical_findings = []
        clauses = [part.strip() for part in re.split(r"[;,]", text) if part.strip()]
        for clause in clauses:
            field = re.match(
                r"^(?P<label>поперечник|размеры|размер|объем|объём|"
                r"стенки(?:\s+пузырьков)?|контуры|структура|эхоструктура)"
                r"\s*[:–—-]?\s*"
                r"(?P<value>.*)$",
                clause,
                re.IGNORECASE,
            )
            if field:
                label = _key(field.group("label"))
                if label.startswith("стенки"):
                    label = "стенки"
                value = _clean(field.group("value"))
                _add_value(entity, label, value)
                if self._is_clinical_statement(value):
                    clinical_findings.append(value)
            elif re.fullmatch(r"поперечник\s+\d[\d.,]*\s*(?:мм|см)", clause, re.I):
                match = re.match(r"поперечник\s+(.+)", clause, re.I)
                assert match is not None
                _add_value(entity, "поперечник", _clean(match.group(1)))
            elif re.search(r"\bне\s+деформирован\w*", clause, re.I):
                _add_value(entity, "состояние", clause)
                clinical_findings.append(clause)
            elif clause:
                self._append_list(entity, "наблюдения", clause)
                if self._is_clinical_statement(clause):
                    clinical_findings.append(clause)
        return clinical_findings

    @staticmethod
    def _is_empty_label(line: str, label: str) -> bool:
        match = _FIELD.match(line)
        return bool(match and _key(match.group(1)) == label and not _clean(match.group(2)))

    @staticmethod
    def _starts_new_structure_field(line: str) -> bool:
        if any(pattern.match(line) for pattern, _ in _PROSTATE_ENTITY_LINES):
            return True
        field = _FIELD.match(line)
        if field and _key(field.group(1)) in _FIELD_LABELS:
            return True
        if _PROPERTY_PREFIX.match(line):
            return True
        return bool(
            re.match(r"^(?:размеры|размер|объем|объём)\s+.+$", line, re.I)
        )

    @staticmethod
    def _split_labeled_clauses(line: str) -> list[str]:
        parts = []
        start = 0
        for match in re.finditer(r",\s*(?=[^,:\n]{1,60}:\s*)", line):
            if ":" not in line[start : match.start()]:
                continue
            parts.append(line[start : match.start()].strip())
            start = match.start() + 1
        if parts:
            parts.append(line[start:].strip())
            return parts
        return [line]

    @staticmethod
    def _is_clinical_statement(text: str) -> bool:
        return bool(
            re.search(
                r"\b(?:не\s+\w+|без\s+\w+|фиброз\w*|микрокальцин\w*|"
                r"кальцин\w*|кист\w*|узл\w*|стеноз\w*|извит\w*|"
                r"неоднородн\w*)\b",
                text,
                re.IGNORECASE,
            )
        )

    @staticmethod
    def _parse_measurement_value(value: str) -> str | dict[str, str]:
        match = re.match(
            r"^(?P<value>[\d.,]+\s*(?:мм|см3|см³|мл|см)?)(?:\s*\((?P<ref>.*)\))?$",
            value,
            re.IGNORECASE,
        )
        if not match:
            return {"значение": value}
        parsed_value = _clean(match.group("value"))
        if match.group("ref"):
            parsed = {"значение": parsed_value}
            parsed["референс"] = _clean(match.group("ref"))
            return parsed
        return parsed_value

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
        current = target.get(key)
        if current is None:
            target[key] = [value]
        elif isinstance(current, list):
            current.append(value)
        else:
            target[key] = [current, value]
