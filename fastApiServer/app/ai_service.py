import os
import json
from typing import Dict, List, Optional
from openai import OpenAI
from dotenv import load_dotenv
from pathlib import Path

# Try to load .env file from multiple possible locations
# Docker Compose sets env_file, but we also try to load .env for local development

# 1. Try loading from project root (for local development: ./fastApiServer/../.env)
try:
    project_root = Path(__file__).parent.parent.parent
    env_path = project_root / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
except Exception:
    pass

# 2. Try loading from current directory
try:
    load_dotenv(override=False)
except Exception:
    pass

# Get API key from environment (set by docker-compose env_file or .env)
# Docker Compose's env_file should set this automatically
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError(
        "OPENAI_API_KEY environment variable is not set. "
        "Please ensure your .env file exists in the project root and docker-compose.yml has 'env_file: - .env' configured."
    )

client = OpenAI(api_key=api_key)
model = "gpt-4o-mini"

# Default characters for the game
DEFAULT_CHARACTERS = [
    {"name": "Cersei Lannister", "trust_level": 0, "threat_level": "high"},
    {"name": "Joffrey Baratheon", "trust_level": 0, "threat_level": "high"},
    {"name": "Varys", "trust_level": 3, "threat_level": "medium"},
    {"name": "Littlefinger", "trust_level": 2, "threat_level": "medium"},
]


def generate_initial_scene() -> Dict:
    """Generate the starting scene for the game."""
    prompt = """You are writing a scene for "Escape King's Landing", a visual novel game where Ned Stark must escape King's Landing after Robert's death.

Generate the opening scene. Ned Stark is in King's Landing after Robert Baratheon's death. He needs to escape the city alive.

Return a JSON object with:
- scene_setting: A brief location name (e.g., "Ned's chambers", "Red Keep throne room")
- narrative: 2-3 sentences describing the current situation and what Ned sees/thinks
- choices: An array of 3-4 choice objects, each with:
  * id: A short unique identifier (e.g., "trust_varys", "confront_cersei")
  * description: What Ned chooses to do (1-2 sentences)
  * risk_level: "low", "medium", or "high"

Stay true to Game of Thrones setting. Ned cannot use violence effectively. Choices should have logical consequences.

Example format:
{
  "scene_setting": "Ned's chambers",
  "narrative": "The morning sun filters through the narrow windows of your chambers in the Red Keep. Robert is dead, and you know the Lannisters will move against you soon. Your honor demands you act, but your survival depends on escaping this city alive.",
  "choices": [
    {"id": "seek_varys", "description": "Send a message to Varys, the Master of Whisperers, seeking information about safe passage out of the city.", "risk_level": "medium"},
    {"id": "gather_allies", "description": "Reach out to your remaining allies in the city to form an escape plan.", "risk_level": "low"},
    {"id": "confront_cersei", "description": "Confront Cersei directly about her children's true parentage, hoping to force a resolution.", "risk_level": "high"}
  ]
}"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a creative writer specializing in Game of Thrones fan fiction. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.8
        )
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        # Fallback if AI fails
        return {
            "scene_setting": "Ned's chambers",
            "narrative": "The morning sun filters through the narrow windows of your chambers in the Red Keep. Robert is dead, and you know the Lannisters will move against you soon. Your honor demands you act, but your survival depends on escaping this city alive.",
            "choices": [
                {"id": "seek_varys", "description": "Send a message to Varys, the Master of Whisperers, seeking information about safe passage out of the city.", "risk_level": "medium"},
                {"id": "gather_allies", "description": "Reach out to your remaining allies in the city to form an escape plan.", "risk_level": "low"},
                {"id": "confront_cersei", "description": "Confront Cersei directly about her children's true parentage, hoping to force a resolution.", "risk_level": "high"}
            ]
        }


def generate_continuation(game_state: Dict, choice_id: str) -> Dict:
    """Generate the next turn based on player's choice."""
    turn_number = game_state.get("turn_number", 0) + 1
    previous_turns = game_state.get("previous_turns", [])
    characters = game_state.get("characters", DEFAULT_CHARACTERS.copy())
    key_events = game_state.get("key_events", [])
    ned_status = game_state.get("ned_status", {
        "location": "Red Keep",
        "allies": [],
        "resources": [],
        "physical_state": "healthy"
    })
    
    # Use the choice_description directly (passed from the endpoint)
    choice_description = choice_id  # choice_id is actually the description in our updated flow
    
    # Check for game end conditions
    if turn_number >= 15:
        # Force game end - check if Ned escaped
        if ned_status.get("location") == "Outside King's Landing" or "escaped" in str(ned_status.get("location", "")).lower():
            return {
                "narrative": "Against all odds, you have escaped King's Landing. The city gates are behind you, and the open road stretches ahead. You are alive, and honor has been preserved through survival.",
                "scene_setting": "Outside King's Landing",
                "scene_changed": True,
                "choices": [],
                "characters": characters,
                "game_status": "victory",
                "game_over": True,
                "victory": True
            }
        else:
            return {
                "narrative": "Time has run out. The Lannisters have moved against you, and you find yourself surrounded. Your honor could not save you from the game of thrones.",
                "scene_setting": ned_status.get("location", "Red Keep"),
                "scene_changed": False,
                "choices": [],
                "characters": characters,
                "game_status": "defeat",
                "game_over": True,
                "victory": False
            }
    
    # Get previous narrative from game state
    previous_narrative = game_state.get("current_narrative", "")
    
    # Build context for AI
    context = f"""Previous turns: {len(previous_turns)}
Current location: {ned_status.get('location', 'Unknown')}
Ned's allies: {', '.join(ned_status.get('allies', [])) if ned_status.get('allies') else 'None'}
Key events: {', '.join(key_events) if key_events else 'None'}
Characters and their trust levels: {json.dumps(characters, indent=2)}
Previous narrative: {previous_narrative}
Last choice made: {choice_description}"""

    prompt = f"""You are writing a continuation for "Escape King's Landing", a visual novel game where Ned Stark must escape King's Landing after Robert's death.

Game Context:
{context}

The player just made this choice: {choice_description}

Generate the consequence of this choice and the next scene. Return a JSON object with:
- narrative: 2-3 sentences describing what happens as a result of the choice and the new situation
- scene_setting: A brief location name (may be the same or different from previous)
- scene_changed: boolean indicating if the scene_setting changed
- choices: An array of 3-4 choice objects for the next turn (same format as before)
- characters: Updated array of character objects with trust_level and threat_level
- ned_status: Updated object with location, allies (array of names), resources (array), physical_state
- key_events: Array of major plot points (add any new ones)
- game_status: "active", "victory" (if Ned escaped), or "defeat" (if captured/killed)
- game_over: boolean
- victory: boolean (only true if game_status is "victory")

Rules:
- Stay true to Game of Thrones setting
- Ned cannot use violence effectively
- Choices have logical consequences
- Game ends after 10-15 turns max
- Victory: Ned escapes King's Landing (location becomes "Outside King's Landing" or similar)
- Defeat: Ned is captured/killed
- Update character trust levels based on actions (range 0-10)
- Track key events that affect the story
- If game_over is true, choices should be empty array
- IMPORTANT: Generate NEW and DIFFERENT choices each turn based on the current situation
- Each choice ID must be unique (use descriptive names like "trust_varys", "confront_cersei", etc.)
- Choices should reflect the consequences of previous actions and the current narrative state

Example format:
{{
  "narrative": "Varys responds to your message with cryptic words, suggesting a meeting in the shadows of the Red Keep. He hints at knowledge of secret passages, but warns that time is running short.",
  "scene_setting": "Secret passage",
  "scene_changed": true,
  "choices": [
    {{"id": "follow_varys", "description": "Trust Varys and follow him through the secret passage.", "risk_level": "medium"}},
    {{"id": "demand_info", "description": "Demand more information before proceeding.", "risk_level": "low"}},
    {{"id": "seek_alternate", "description": "Look for another way out without Varys.", "risk_level": "high"}}
  ],
  "characters": [
    {{"name": "Varys", "trust_level": 4, "threat_level": "medium"}},
    ...
  ],
  "ned_status": {{
    "location": "Secret passage",
    "allies": ["Varys"],
    "resources": ["Secret passage knowledge"],
    "physical_state": "healthy"
  }},
  "key_events": ["Contacted Varys", "Learned of secret passages"],
  "game_status": "active",
  "game_over": false,
  "victory": false
}}"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a creative writer specializing in Game of Thrones fan fiction. Always return valid JSON. Make sure all required fields are present."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        
        # Ensure all required fields are present
        result.setdefault("scene_changed", False)
        result.setdefault("game_over", False)
        result.setdefault("victory", False)
        result.setdefault("game_status", "active")
        
        # Ensure choices are present and valid (unless game is over)
        if not result.get("game_over", False):
            current_turn = game_state.get("turn_number", 0) + 1
            if not result.get("choices") or not isinstance(result.get("choices"), list) or len(result.get("choices", [])) == 0:
                # Generate fallback choices if missing
                result["choices"] = [
                    {"id": f"choice_{current_turn}_1", "description": "Continue forward cautiously.", "risk_level": "medium"},
                    {"id": f"choice_{current_turn}_2", "description": "Look for allies or information.", "risk_level": "low"},
                    {"id": f"choice_{current_turn}_3", "description": "Take a risky but potentially rewarding action.", "risk_level": "high"}
                ]
        print(result)
        return result
    except Exception as e:
        # Fallback if AI fails
        print(e)
        return {
            "narrative": "Your choice leads to uncertain consequences. The game of thrones continues, and you must navigate carefully.",
            "scene_setting": ned_status.get("location", "Red Keep"),
            "scene_changed": False,
            "choices": [
                {"id": "continue_1", "description": "Continue forward cautiously.", "risk_level": "medium"},
                {"id": "continue_2", "description": "Look for allies.", "risk_level": "low"},
                {"id": "continue_3", "description": "Take a risky action.", "risk_level": "high"}
            ],
            "characters": characters,
            "game_status": "active",
            "game_over": False,
            "victory": False
        }


def generate_art_description(scene_setting: str, curr_narrative: str) -> Dict:
    """Generate a detailed visual description of the current scene."""
    prompt = f"""Generate a detailed visual description for a scene in "Escape King's Landing", a Game of Thrones visual novel.

Scene setting: {scene_setting}
Current narrative: {curr_narrative}
Return a JSON object with:
- art_description: 2-3 sentences describing the scene according to the current narrative and scene setting. Include lighting, mood, key visual elements, characters, character positions, atmosphere. Use cinematic Game of Thrones aesthetic - detailed and immersive. Be creative.
- style_notes: Brief notes about the visual style (e.g., "Medieval fantasy, tense atmosphere, warm afternoon lighting")

Example format:
{{
  "art_description": "The Red Keep's throne room looms before you, its high vaulted ceilings casting long shadows across the cold stone floor. Cersei sits regally on the Iron Throne, surrounded by Lannister guards in crimson cloaks, their hands resting on sword hilts. The afternoon light streams through narrow windows, illuminating dust motes and the glint of steel.",
  "style_notes": "Medieval fantasy, tense atmosphere, warm afternoon lighting"
}}"""
    print(scene_setting)
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a visual artist and writer specializing in atmospheric scene descriptions. Always return valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"}
        )
        result = json.loads(response.choices[0].message.content)
        print("result", result)
        return result
    except Exception as e:
        print(e)
        # Fallback if AI fails
        return {
            "art_description": f"The {scene_setting} stretches before you, its ancient stone walls bearing witness to centuries of intrigue and power. The atmosphere is tense, with shadows playing across the surfaces and the weight of history pressing down.",
            "style_notes": "Medieval fantasy, atmospheric, dramatic lighting"
        }


