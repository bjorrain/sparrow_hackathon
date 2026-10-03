"""Convert internal report extraction into the frontend response schema."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any, Literal

from sparrow.backend.parsers.clinical_parser import ClinicalDescriptionParser

FrontendStatus = Literal["норма", "подозрение", "патология"]

_SIZE_FIELDS = {
    "размер",
    "размеры",
    "объем",
    "длина",
    "ширина",
    "высота",
    "толщина",
    "диаметр",
    "поперечник",
    "длинник",
    "квр",
    "вр",
    "площадь",
    "головка",
    "тело",
    "хвост",
}
_MEASUREMENT_KEYS = {"значение", "референс"}
_SIZE_WITH_FEATURE = re.compile(
    r"^(?P<size>.*?(?:кв\.?\s*см|мм|см(?:2|²|3|³)?|мл|м))\s*[,;]\s*"
    r"(?P<feature>[^0-9].+)$",
    re.IGNORECASE,
)


def to_frontend_schema(
    report: Mapping[str, Any],
    clinical_parser: ClinicalDescriptionParser,
) -> dict[str, Any]:
    """Transform the rule-based report result into the stable UI contract."""
    raw_structures = report.get("структуры", {})
    if not isinstance(raw_structures, Mapping):
        raise ValueError("Поле структуры должно быть объектом")

    structures: list[dict[str, Any]] = []
    for name, data in raw_structures.items():
        if isinstance(data, Mapping):
            _append_structure(structures, str(name), data, clinical_parser)
        else:
            _append_structure(
                structures, str(name), {"наблюдения": [str(data)]}, clinical_parser
            )

    raw_sides = report.get("стороны", {})
    if isinstance(raw_sides, Mapping):
        for side, data in raw_sides.items():
            if isinstance(data, Mapping):
                vessels = data.get("сосуды")
                if isinstance(vessels, Mapping):
                    side_observations = data.get("наблюдения")
                    for vessel_name, vessel_data in vessels.items():
                        if not isinstance(vessel_data, Mapping):
                            continue
                        vessel = dict(vessel_data)
                        if side_observations:
                            vessel["наблюдения"] = side_observations
                        _append_structure(
                            structures,
                            f"{vessel_name} {side}",
                            vessel,
                            clinical_parser,
                        )
                else:
                    _append_structure(
                        structures, f"сосуды {side}", data, clinical_parser
                    )

    other_findings = report.get("прочие_находки", [])
    if other_findings:
        observations = (
            other_findings if isinstance(other_findings, list) else [other_findings]
        )
        _append_structure(
            structures,
            "прочие находки",
            {"наблюдения": observations},
            clinical_parser,
        )

    metadata = report.get("служебная_информация", {})
    if not isinstance(metadata, Mapping):
        metadata = {}
    return {
        "structures": structures,
        "technical_data": dict(metadata),
        "conclusion": {
            "text": report.get("заключение"),
            "recommendations": report.get("рекомендации"),
        },
    }


def _append_structure(
    output: list[dict[str, Any]],
    name: str,
    data: Mapping[str, Any],
    clinical_parser: ClinicalDescriptionParser,
) -> None:
    size_parts: list[str] = []
    morphology: dict[str, Any] = {}
    nested_structures: list[tuple[str, Mapping[str, Any]]] = []

    for key, value in data.items():
        field_name = str(key)
        if isinstance(value, Mapping) and _is_nested_structure(field_name, value):
            nested_structures.append((field_name, value))
            continue
        if _is_size_field(field_name, value):
            formatted = _format_value(value)
            split = _SIZE_WITH_FEATURE.match(formatted)
            size_label = field_name.replace("_", " ")
            generic_size_label = field_name.casefold().replace("ё", "е") in {
                "размер",
                "размеры",
                "объем",
                "длина",
                "ширина",
                "высота",
                "толщина",
                "диаметр",
                "поперечник",
                "длинник",
                "квр",
                "вр",
                "площадь",
                "головка",
                "тело",
                "хвост",
            }
            if split:
                size_parts.append(
                    _format_size_value(size_label, split.group("size").strip(), generic_size_label)
                )
                feature = split.group("feature").strip()
                feature_key = (
                    "форма"
                    if re.search(r"\bформ\w*", feature, re.IGNORECASE)
                    else "описание_размеров"
                )
                morphology[feature_key] = feature
            else:
                size_parts.append(
                    _format_size_value(size_label, formatted, generic_size_label)
                )
        else:
            morphology[field_name] = value

    statuses = {
        status
        for text in _collect_text(morphology)
        if (status := clinical_parser.classify_status(text)) is not None
    }
    if "патология" in statuses:
        status: FrontendStatus = "патология"
    elif "изменение" in statuses:
        status = "подозрение"
    else:
        status = "норма"

    output.append(
        {
            "name": name.replace("_", " "),
            "size": "; ".join(part for part in size_parts if part),
            "morphology": morphology,
            "status": status,
        }
    )
    for child_name, child_data in nested_structures:
        _append_structure(
            output, f"{name} / {child_name}", child_data, clinical_parser
        )


def _is_measurement(value: Mapping[str, Any]) -> bool:
    return bool(value) and set(value).issubset(_MEASUREMENT_KEYS) and "значение" in value


def _is_nested_structure(field_name: str, value: Mapping[str, Any]) -> bool:
    return field_name != "измерения" and not _is_measurement(value)


def _is_size_field(name: str, value: Any) -> bool:
    normalized = name.casefold().replace("ё", "е")
    if normalized.startswith("толщина") and not re.search(r"\d", _format_value(value)):
        return False
    return normalized in _SIZE_FIELDS or normalized.startswith(
        ("размер", "толщина")
    ) or normalized.endswith(
        (
            "_толщина",
            "_диаметр",
            "_длинник",
            "_поперечник",
            "_квр",
            "_вр",
            "_площадь",
            "_головка",
            "_тело",
            "_хвост",
        )
    )


def _format_value(value: Any) -> str:
    if _is_measurement(value):
        amount = str(value["значение"])
        reference = value.get("референс")
        return f"{amount} ({reference})" if reference else amount
    if isinstance(value, list):
        return ", ".join(_format_value(item) for item in value)
    if isinstance(value, Mapping):
        return ", ".join(f"{key}: {_format_value(item)}" for key, item in value.items())
    return str(value)


def _format_size_value(label: str, value: str, generic_label: bool) -> str:
    return value if generic_label else f"{label}: {value}"


def _collect_text(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [text for item in value.values() for text in _collect_text(item)]
    if isinstance(value, list):
        return [text for item in value for text in _collect_text(item)]
    return []
