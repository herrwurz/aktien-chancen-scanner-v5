from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class DetectiveRequest(BaseModel):
    teaser_text: str = Field(default="", max_length=20_000)
    screenshot_base64: str | None = Field(default=None, max_length=3_000_000)
    screenshot_media_type: str | None = None
    publication_at: datetime | None = None
    known_hints: list[str] = Field(default_factory=list, max_length=20)

    @model_validator(mode="after")
    def require_input(self):
        if not self.teaser_text.strip() and not self.screenshot_base64:
            raise ValueError("teaser text or screenshot required")
        if self.screenshot_base64 and not self.screenshot_media_type:
            raise ValueError("screenshot media type required")
        return self
