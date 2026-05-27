from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message:         str          = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None   = None
    model_override:  str | None   = None
    temperature:     float | None = Field(None, ge=0.0, le=2.0)
    max_tokens:      int | None   = Field(None, ge=1, le=4096)
    top_p:           float | None = Field(None, ge=0.0, le=1.0)
    compare:         bool         = False
    image_b64:       str | None   = Field(None, max_length=2_097_152)
    image_mime_type: str | None   = None
    workspace_id:    str | None   = None
