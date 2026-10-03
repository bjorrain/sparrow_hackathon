"""FastAPI endpoints for extracting clinical findings from report text."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from sparrow.backend.parsers.clinical_parser import ClinicalDescriptionParser
from sparrow.backend.parsers.clinical_structure import ClinicalStructureParser

Status = Literal["норма", "изменение", "патология"]
Urgency = Literal["норма", "планово", "срочно", "неотложно"]


class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=100_000)]

    @field_validator("text")
    @classmethod
    def text_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Текст описания не должен быть пустым")
        return value


class FindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str
    lemmas: list[str]
    status: Status
    status_rule: str
    urgency: Urgency
    urgency_rule: str


class StructuredReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    service_info: dict[str, Any] = Field(alias="служебная_информация")
    organs: dict[str, dict[str, Any]] = Field(alias="органы")
    other_findings: list[str] = Field(alias="прочие_находки")
    conclusion: str | None = Field(alias="заключение")
    recommendations: str | None = Field(alias="рекомендации")


class ExtractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    findings: list[FindingResponse]
    structured_data: StructuredReportResponse


def get_parser(request: Request) -> ClinicalDescriptionParser:
    parser = getattr(request.app.state, "clinical_parser", None)
    if parser is None:
        raise HTTPException(
            status_code=503,
            detail="Парсер клинических описаний еще не готов",
        )
    return parser


def get_structure_parser(request: Request) -> ClinicalStructureParser:
    parser = getattr(request.app.state, "clinical_structure_parser", None)
    if parser is None:
        raise HTTPException(
            status_code=503,
            detail="Структурный парсер еще не готов",
        )
    return parser


def create_app(
    parser: ClinicalDescriptionParser | None = None,
    structure_parser: ClinicalStructureParser | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        application.state.clinical_parser = (
            parser if parser is not None else ClinicalDescriptionParser()
        )
        application.state.clinical_structure_parser = (
            structure_parser
            if structure_parser is not None
            else ClinicalStructureParser()
        )
        yield
        del application.state.clinical_parser
        del application.state.clinical_structure_parser

    application = FastAPI(
        title="Sparrow Clinical Findings API",
        description=(
            "Извлечение фрагментов клинических описаний с эвристической "
            "классификацией статуса и срочности."
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    @application.post(
        "/extract",
        response_model=ExtractResponse,
        summary="Извлечь находки из описания",
    )
    def extract(
        body: ExtractRequest,
        clinical_parser: Annotated[
            ClinicalDescriptionParser, Depends(get_parser)
        ],
        report_parser: Annotated[
            ClinicalStructureParser, Depends(get_structure_parser)
        ],
    ) -> dict[str, Any]:
        return {
            **clinical_parser.parse(body.text),
            "structured_data": report_parser.parse(body.text),
        }

    return application


app = create_app()
