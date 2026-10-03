"""Rule-based extraction and classification of findings in Russian descriptions."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Literal

from natasha import Doc, MorphVocab, NewsEmbedding, NewsMorphTagger, Segmenter

FindingStatus = Literal["норма", "изменение", "патология"]
Urgency = Literal["норма", "планово", "срочно", "неотложно"]

_STATUS_TERMS: dict[FindingStatus, tuple[str, ...]] = {
    "патология": (
        "патология",
        "патологический",
        "киста",
        "узел",
        "стеноз",
        "атеросклероз",
        "атеросклеротический",
        "бляшка",
        "асб",
        "тромб",
        "опухоль",
        "образование",
        "гиперплазия",
        "кровоизлияние",
        "перелом",
        "полип",
        "миома",
        "кальцинат",
        "кальцинация",
        "варикоз",
        "грыжа",
        "камень",
        "конкремент",
        "воспаление",
        "фиброз",
        "аденома",
        "окклюзия",
        "аневризма",
    ),
    "изменение": (
        "изменение",
        "изменить",
        "увеличенный",
        "увеличить",
        "уменьшенный",
        "уменьшить",
        "расширенный",
        "расширить",
        "утолщенный",
        "утолстить",
        "истонченный",
        "истоншить",
        "повышенный",
        "повысить",
        "сниженный",
        "снизить",
        "неоднородный",
        "уплотненный",
        "уплотнить",
        "деформированный",
        "деформировать",
        "нарушенный",
        "нарушить",
        "диффузный",
        "очаговый",
        "смещенный",
        "отклонение",
    ),
    "норма": (
        "нормальный",
        "в норме",
        "в пределах нормы",
        "предел нормы",
        "сохраненный",
        "проходимый",
        "не выявить",
        "не обнаружить",
        "не определяться",
        "без патологии",
        "без изменения",
    ),
}

_DEFAULT_URGENCY_TERMS: dict[Urgency, tuple[str, ...]] = {
    "неотложно": (
        "неотложно",
        "неотложный",
        "немедленно",
        "экстренная помощь",
        "вызвать скорую",
    ),
    "срочно": (
        "срочно",
        "срочный",
        "экстренно",
        "экстренный",
        "безотлагательно",
    ),
    "планово": (
        "планово",
        "плановый",
        "плановая консультация",
    ),
    "норма": (),
}

_CLAUSE_SEPARATOR = re.compile(r";+|\n+|(?<=[.!?])\s+|,\s+(?=[А-Яа-яЁё])")
_SIDE_LABEL = re.compile(
    r"^(?:справа|слева|правый|правая|правое|левый|левая|левое)\s*:?\s*$",
    re.IGNORECASE,
)
_SPACE = re.compile(r"\s+")
_URGENCY_ORDER: tuple[Urgency, ...] = (
    "неотложно",
    "срочно",
    "планово",
    "норма",
)


def _split_clauses(text: str) -> list[str]:
    parts = [part.strip() for part in _CLAUSE_SEPARATOR.split(text) if part.strip()]
    clauses = []
    side_prefix = None
    for part in parts:
        if _SIDE_LABEL.fullmatch(part):
            side_prefix = part
            continue
        if side_prefix:
            part = f"{side_prefix} {part}"
            side_prefix = None
        clauses.append(part)
    return clauses


class ClinicalDescriptionParser:
    """Extract text fragments and assign heuristic status and urgency labels.

    Natasha supplies Russian tokenization and lemmatization. The clinical
    categories are transparent keyword rules, not a diagnostic model.
    """

    def __init__(
        self,
        urgency_rules: Mapping[Urgency, Sequence[str]] | None = None,
    ) -> None:
        self._segmenter = Segmenter()
        self._morph_vocab = MorphVocab()
        self._morph_tagger = NewsMorphTagger(NewsEmbedding())
        self._urgency_terms = {
            level: list(terms) for level, terms in _DEFAULT_URGENCY_TERMS.items()
        }
        if urgency_rules:
            for level, terms in urgency_rules.items():
                if level not in self._urgency_terms:
                    raise ValueError(f"Неизвестная степень срочности: {level}")
                self._urgency_terms[level].extend(terms)
        self._status_patterns = {
            status: [self._lemmatize(term) for term in terms]
            for status, terms in _STATUS_TERMS.items()
        }
        self._urgency_patterns = {
            level: [self._lemmatize(term) for term in terms]
            for level, terms in self._urgency_terms.items()
        }

    def parse(self, description: str) -> dict[str, list[dict[str, object]]]:
        """Return clauses as findings with Russian status and urgency labels."""
        if not isinstance(description, str):
            raise TypeError("description должен быть строкой")

        findings = []
        for clause in _split_clauses(description):
            lemmas = self._lemmatize(clause)
            if not lemmas:
                continue
            status, _ = self._classify_status(lemmas)
            urgency, _ = self._classify_urgency(lemmas, status)
            findings.append({
                "summary": clause,
                "status": status,
                "urgency": urgency,
            })
        return {"findings": findings}

    def _lemmatize(self, text: str) -> list[str]:
        normalized = _SPACE.sub(" ", text.lower().replace("ё", "е")).strip()
        if not normalized:
            return []
        doc = Doc(normalized)
        doc.segment(self._segmenter)
        doc.tag_morph(self._morph_tagger)
        for token in doc.tokens:
            token.lemmatize(self._morph_vocab)
        return [token.lemma for token in doc.tokens if token.lemma]

    @staticmethod
    def _contains_phrase(lemmas: list[str], phrase: list[str]) -> bool:
        if not phrase or len(phrase) > len(lemmas):
            return False
        return any(
            lemmas[index : index + len(phrase)] == phrase
            for index in range(len(lemmas) - len(phrase) + 1)
        )

    def _positive_status_matches(
        self, lemmas: list[str], status: FindingStatus
    ) -> list[str]:
        matches = []
        for phrase, pattern in zip(
            self._status_terms_for(status), self._status_patterns[status]
        ):
            if not self._contains_phrase(lemmas, pattern):
                continue
            if status in ("патология", "изменение") and self._is_negated(
                lemmas, pattern
            ):
                continue
            matches.append(phrase)
        return matches

    def _is_negated(self, lemmas: list[str], phrase: list[str]) -> bool:
        negative_verbs = {
            "выявить",
            "обнаружить",
            "определить",
            "определяться",
            "визуализировать",
            "лоцироваться",
        }
        for index in range(len(lemmas) - len(phrase) + 1):
            if lemmas[index : index + len(phrase)] != phrase:
                continue
            before = lemmas[max(0, index - 5) : index]
            after = lemmas[index + len(phrase) : index + len(phrase) + 5]
            if any(
                token in {"без", "отсутствовать", "отсутствие", "нет"}
                for token in before
            ):
                return True
            if before and before[-1] in {"не", "ни"}:
                return True
            if any(
                token in {"отсутствовать", "отсутствие", "нет"} for token in after[:2]
            ):
                return True
            if any(
                before[position] in {"не", "ни"}
                and position + 1 < len(before)
                and before[position + 1] in negative_verbs
                for position in range(len(before))
            ):
                return True
            if any(
                after[position] in {"не", "ни"}
                and position + 1 < len(after)
                and after[position + 1] in negative_verbs
                for position in range(len(after))
            ):
                return True
        return False

    @staticmethod
    def _status_terms_for(status: FindingStatus) -> tuple[str, ...]:
        return _STATUS_TERMS[status]

    def _classify_status(self, lemmas: list[str]) -> tuple[FindingStatus, str]:
        pathology_matches = self._positive_status_matches(lemmas, "патология")
        if pathology_matches:
            return "патология", pathology_matches[0]
        if any(
            self._contains_phrase(lemmas, pattern) and self._is_negated(lemmas, pattern)
            for pattern in self._status_patterns["патология"]
        ):
            return "норма", "отрицание_патологической_находки"
        change_matches = self._positive_status_matches(lemmas, "изменение")
        if change_matches:
            return "изменение", change_matches[0]
        if any(
            self._contains_phrase(lemmas, pattern) and self._is_negated(lemmas, pattern)
            for pattern in self._status_patterns["изменение"]
        ):
            return "норма", "отрицание_изменения"
        normal_matches = self._positive_status_matches(lemmas, "норма")
        if normal_matches:
            return "норма", normal_matches[0]
        return "изменение", "описанный_фрагмент_без_совпадения_с_правилами"

    def _classify_urgency(
        self, lemmas: list[str], status: FindingStatus
    ) -> tuple[Urgency, str]:
        for level in _URGENCY_ORDER:
            for phrase, pattern in zip(
                self._urgency_terms[level], self._urgency_patterns[level]
            ):
                matched = self._contains_phrase(lemmas, pattern)
                negated = self._is_negated_urgency(lemmas, pattern)
                if matched and not negated:
                    return level, phrase
        if status == "норма":
            return "норма", "статус_норма_без_указания_срочности"
        return "планово", "по_умолчанию_без_указания_срочности"

    def _is_negated_urgency(self, lemmas: list[str], phrase: list[str]) -> bool:
        for index in range(len(lemmas) - len(phrase) + 1):
            if lemmas[index : index + len(phrase)] != phrase:
                continue
            before = lemmas[max(0, index - 2) : index]
            if any(token in {"не", "ни", "без", "нет"} for token in before):
                return True
        return False
