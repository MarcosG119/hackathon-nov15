from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel


class Choice(BaseModel):
    id: str
    description: str
    risk_level: str


class Character(BaseModel):
    name: str
    trust_level: int
    threat_level: str


class StartGameRequest(BaseModel):
    pass  # Empty request body - no parameters needed


class StartGameResponse(BaseModel):
    session_id: str
    scene_setting: str
    narrative: str
    choices: List[Choice]
    characters: List[Character]
    game_status: str


class ContinueGameRequest(BaseModel):
    session_id: str
    choice_id: str


class ContinueGameResponse(BaseModel):
    narrative: str
    scene_setting: str
    scene_changed: bool
    choices: List[Choice]
    characters: List[Character]
    game_status: str
    game_over: bool
    victory: bool


class GenerateArtRequest(BaseModel):
    session_id: str
    scene_setting: str
    curr_narrative: str


class GenerateArtResponse(BaseModel):
    art_description: str
    style_notes: str


class GenerateImageRequest(BaseModel):
    art_description: str
    style_notes: Optional[str] = ""


class GenerateImageResponse(BaseModel):
    image_url: Optional[str] = None
    error: Optional[str] = None


class GenerateVoiceRequest(BaseModel):
    text: str
    voice_id: str
