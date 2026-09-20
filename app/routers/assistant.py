"""Permission-aware deterministic assistant endpoints."""
from __future__ import annotations

# pyrefly: ignore [missing-import]
from fastapi import APIRouter, Depends, HTTPException

from app.auth import User, require_user
from app.services import assistant
from app.services.language import supported_languages

router = APIRouter(prefix="/assistant", tags=["assistant"])


@router.get("/languages")
def languages(_: User = Depends(require_user)) -> list[dict[str, str]]:
    return supported_languages()


def _handle(user: User, body: assistant.AssistantMessage) -> assistant.AssistantResponse:
    try:
        return assistant.handle(user, body)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ValueError, assistant.kaam.KaamError, assistant.booking_flow.BookingFlowError) as exc:
        status = getattr(exc, "status", getattr(exc, "status_code", 422))
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/message", response_model=assistant.AssistantResponse)
def message(body: assistant.AssistantMessage, user: User = Depends(require_user)) -> assistant.AssistantResponse:
    return _handle(user, body)


from pydantic import BaseModel
from app.services.gemini_nlp import parse_voice_query


class VoiceParseRequest(BaseModel):
    query: str
    language: str = "hi"


@router.post("/parse-query")
def parse_query_endpoint(body: VoiceParseRequest) -> dict:
    """Parse multilingual Hindi/Hinglish/English voice transcript into structured booking intent."""
    return parse_voice_query(transcript=body.query, language=body.language)


@router.post("/voice", response_model=assistant.AssistantResponse)
def voice(body: assistant.AssistantMessage, user: User = Depends(require_user)) -> assistant.AssistantResponse:
    """Accept speech-to-text supplied by the browser; deterministic text fallback is always available."""
    return _handle(user, body)
