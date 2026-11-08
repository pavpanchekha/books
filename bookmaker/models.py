from __future__ import annotations

import re
from typing import Annotated

from pydantic import BaseModel, Field, field_validator


HexColor = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}$")]


class StoryPage(BaseModel):
    text: str

    @field_validator("text")
    @classmethod
    def tidy_text(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()


class BookDraft(BaseModel):
    title: str
    subtitle: str
    pages: list[StoryPage]

    @field_validator("title", "subtitle")
    @classmethod
    def tidy_heading(cls, value: str) -> str:
        return re.sub(r"\s+", " ", value).strip()

    @field_validator("pages")
    @classmethod
    def exactly_six_pages(cls, value: list[StoryPage]) -> list[StoryPage]:
        if len(value) != 6:
            raise ValueError("a book must have exactly six content pages")
        return value


class Palette(BaseModel):
    body_background: HexColor
    ink: HexColor
    paper: HexColor
    heading: HexColor
    accent: HexColor
    subtitle: HexColor
    active_dot: HexColor
    focus: HexColor
    copy_backgrounds: list[HexColor]

    @field_validator("copy_backgrounds")
    @classmethod
    def seven_backgrounds(cls, value: list[str]) -> list[str]:
        if len(value) != 7:
            raise ValueError("need one copy background for each of seven pages")
        return value


class Scene(BaseModel):
    page_number: int = Field(ge=1, le=7)
    filename: str = Field(pattern=r"^[0-9]{2}-[a-z0-9-]+\.png$")
    scene: str


class VisualPlan(BaseModel):
    visual_bible: str
    palette: Palette
    scenes: list[Scene]

    @field_validator("scenes")
    @classmethod
    def all_seven_scenes(cls, value: list[Scene]) -> list[Scene]:
        if [scene.page_number for scene in value] != list(range(1, 8)):
            raise ValueError("scenes must be ordered pages 1 through 7")
        if len({scene.filename for scene in value}) != 7:
            raise ValueError("scene filenames must be unique")
        return value


class EditorialReview(BaseModel):
    revised: BookDraft
    notes: list[str]


class ArtDirectionReview(BaseModel):
    revised: VisualPlan
    notes: list[str]


class ImageReview(BaseModel):
    page_number: int = Field(ge=1, le=7)
    passed: bool
    issues: list[str]
    regeneration_instruction: str


class ImageReviewReport(BaseModel):
    pages: list[ImageReview]

    @field_validator("pages")
    @classmethod
    def all_seven_pages(cls, value: list[ImageReview]) -> list[ImageReview]:
        if sorted(page.page_number for page in value) != list(range(1, 8)):
            raise ValueError("review must contain each page exactly once")
        return sorted(value, key=lambda page: page.page_number)


class Translation(BaseModel):
    word: str
    chinese: str


class TranslationSet(BaseModel):
    translations: list[Translation]

