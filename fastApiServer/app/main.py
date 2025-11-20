from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from uuid import UUID
from .model import ClickCount, GameSession, SessionDep, create_db_and_tables
from .schemas import (
    StartGameResponse,
    ContinueGameRequest, ContinueGameResponse,
    GenerateArtRequest, GenerateArtResponse,
    GenerateImageRequest, GenerateImageResponse,
    GenerateVoiceRequest
)
from .ai_service import generate_initial_scene, generate_continuation, generate_art_description
from .image_service import generate_image_with_cache, load_cache_metadata
from .voice_service import generate_voice_stream
from pathlib import Path


app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def _get_user_agent_ip(request: Request) -> str:
    user_agent = request.headers.get("user-agent", "unknown")
    client_ip = request.client.host if request.client else "unknown"
    return f"{client_ip}:{user_agent}"


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/api/cache/status")
def get_cache_status():
    """Get cache status and statistics."""
    import os
    
    cache_metadata = load_cache_metadata()
    project_root = Path(__file__).parent.parent.parent
    cache_dir = project_root / "image_cache"
    metadata_file = project_root / "cache_metadata.json"
    
    # Count actual image files
    image_count = 0
    total_size = 0
    if cache_dir.exists():
        for file in cache_dir.glob("img_*.png"):
            if file.is_file():
                image_count += 1
                total_size += file.stat().st_size
    
    return {
        "cache_entries": len(cache_metadata),
        "image_files": image_count,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "cache_directory": str(cache_dir),
        "metadata_file_exists": metadata_file.exists()
    }


@app.get("/clickcount")
def get_click_count(request: Request, session: SessionDep):
    key = _get_user_agent_ip(request)
    click_count = session.get(ClickCount, key)
    if click_count is None:
        click_count = ClickCount(user_agent_ip=key, click_count=0)
        session.add(click_count)
        session.commit()
        session.refresh(click_count)
    return {"user_agent_ip": key, "click_count": click_count.click_count}


@app.get("/clickcount/increment")
def increment_click_count(request: Request, session: SessionDep):
    key = _get_user_agent_ip(request)

    click_count = session.get(ClickCount, key)
    if click_count is None:
        click_count = ClickCount(user_agent_ip=key, click_count=1)
        session.add(click_count)
    else:
        click_count.click_count += 1

    session.commit()
    session.refresh(click_count)

    return {"user_agent_ip": key, "click_count": click_count.click_count}


# Game API Endpoints

@app.post("/api/game/start", response_model=StartGameResponse)
def start_game(session: SessionDep):
    """Start a new game session."""
    # Generate initial scene using AI
    initial_scene = generate_initial_scene()
    
    # Initialize game state
    game_state = {
        "turn_number": 0,
        "previous_turns": [],
        "characters": initial_scene.get("characters", [
            {"name": "Cersei Lannister", "trust_level": 0, "threat_level": "high"},
            {"name": "Joffrey Baratheon", "trust_level": 0, "threat_level": "high"},
            {"name": "Varys", "trust_level": 3, "threat_level": "medium"},
            {"name": "Littlefinger", "trust_level": 2, "threat_level": "medium"},
        ]),
        "key_events": [],
        "ned_status": {
            "location": initial_scene.get("scene_setting", "Red Keep"),
            "allies": [],
            "resources": [],
            "physical_state": "healthy"
        }
    }
    
    # Create game session
    game_session = GameSession(
        game_state=game_state,
        current_scene_setting=initial_scene.get("scene_setting", ""),
        game_status="active"
    )
    session.add(game_session)
    session.commit()
    session.refresh(game_session)
    
    # Store current narrative and choices in game_state for next turn
    game_state["current_narrative"] = initial_scene.get("narrative", "")
    game_state["current_choices"] = initial_scene.get("choices", [])
    game_session.game_state = game_state
    session.commit()
    
    return StartGameResponse(
        session_id=str(game_session.session_id),
        scene_setting=initial_scene.get("scene_setting", ""),
        narrative=initial_scene.get("narrative", ""),
        choices=initial_scene.get("choices", []),
        characters=initial_scene.get("characters", game_state["characters"]),
        game_status="active"
    )


@app.post("/api/game/continue", response_model=ContinueGameResponse)
def continue_game(request: ContinueGameRequest, session: SessionDep):
    """Continue the game with a player choice."""
    try:
        session_id = UUID(request.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")
    
    # Get game session
    game_session = session.get(GameSession, session_id)
    if game_session is None:
        raise HTTPException(status_code=404, detail="Game session not found")
    
    if game_session.game_status != "active":
        raise HTTPException(status_code=400, detail="Game session is not active")
    
    # Get current game state
    game_state = game_session.game_state
    turn_number = game_state.get("turn_number", 0)
    
    # Get the current narrative and choices from the last response (stored in game_state)
    current_narrative = game_state.get("current_narrative", "")
    current_choices = game_state.get("current_choices", [])
    
    # Find the choice description
    choice_description = "Unknown choice"
    for choice in current_choices:
        if choice.get("id") == request.choice_id:
            choice_description = choice.get("description", "Unknown choice")
            break
    
    # Store current turn in previous_turns before processing choice
    current_turn = {
        "turn": turn_number,
        "scene_setting": game_session.current_scene_setting,
        "narrative": current_narrative,
        "player_choice": request.choice_id,
        "choice_description": choice_description,
        "consequence": None  # Will be filled by AI
    }
    
    # Generate continuation using AI
    continuation = generate_continuation(game_state, choice_description)
    
    # Ensure choices are present and valid
    if not continuation.get("choices") or len(continuation.get("choices", [])) == 0:
        # If no choices returned and game is not over, use fallback
        if not continuation.get("game_over", False):
            continuation["choices"] = [
                {"id": "continue_1", "description": "Continue forward cautiously.", "risk_level": "medium"},
                {"id": "continue_2", "description": "Look for allies.", "risk_level": "low"},
                {"id": "continue_3", "description": "Take a risky action.", "risk_level": "high"}
            ]
    
    # Create a new game_state dict to ensure proper update
    updated_game_state = dict(game_state)  # Create a copy
    updated_game_state["turn_number"] = turn_number + 1
    updated_game_state["previous_turns"] = list(game_state.get("previous_turns", []))
    updated_game_state["previous_turns"].append({
        **current_turn,
        "consequence": continuation.get("narrative", "")
    })
    # Store current narrative and choices for next turn
    updated_game_state["current_narrative"] = continuation.get("narrative", "")
    updated_game_state["current_choices"] = continuation.get("choices", [])
    updated_game_state["characters"] = continuation.get("characters", game_state.get("characters", []))
    updated_game_state["key_events"] = continuation.get("key_events", game_state.get("key_events", []))
    updated_game_state["ned_status"] = continuation.get("ned_status", game_state.get("ned_status", {}))
    
    # Update game session with new state
    game_session.game_state = updated_game_state
    game_session.current_scene_setting = continuation.get("scene_setting", game_session.current_scene_setting)
    game_session.game_status = continuation.get("game_status", "active")
    
    session.commit()
    session.refresh(game_session)
    
    return ContinueGameResponse(
        narrative=continuation.get("narrative", ""),
        scene_setting=continuation.get("scene_setting", ""),
        scene_changed=continuation.get("scene_changed", False),
        choices=continuation.get("choices", []),
        characters=continuation.get("characters", []),
        game_status=continuation.get("game_status", "active"),
        game_over=continuation.get("game_over", False),
        victory=continuation.get("victory", False)
    )


@app.post("/api/game/generate-art", response_model=GenerateArtResponse)
def generate_art(request: GenerateArtRequest, session: SessionDep):
    """Generate art description for a scene."""
    try:
        session_id = UUID(request.session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid session_id format")
    
    # Verify session exists (optional check)
    game_session = session.get(GameSession, session_id)
    if game_session is None:
        raise HTTPException(status_code=404, detail="Game session not found")
    
    # Generate art description using AI
    art_data = generate_art_description(request.scene_setting, request.curr_narrative)
    
    return GenerateArtResponse(
        art_description=art_data.get("art_description", ""),
        style_notes=art_data.get("style_notes", "")
    )


@app.post("/api/game/generate-image", response_model=GenerateImageResponse)
def generate_scene_image(request: GenerateImageRequest):
    """Generate an image for a scene using Freepik API with semantic caching."""
    try:
        result = generate_image_with_cache(request.art_description, request.style_notes)
        
        # Extract image URL from cached result
        image_url = result.get("image_url")
        
        if not image_url:
            return GenerateImageResponse(
                error="Could not generate or retrieve image"
            )
        
        return GenerateImageResponse(image_url=image_url)
    except Exception as e:
        return GenerateImageResponse(
            error=str(e)
        )

@app.post("/api/game/generate-voice")
def generate_voice(request: GenerateVoiceRequest):
    """
    Generates a voice audio stream for the given text.
    """
    try:
        return StreamingResponse(
            generate_voice_stream(request.text, request.voice_id),
            media_type="audio/mpeg"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
