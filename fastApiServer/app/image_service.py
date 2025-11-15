import os
import requests
from typing import Dict, Optional
from dotenv import load_dotenv

load_dotenv()

# FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY", "")
FREEPIK_API_URL = "https://api.freepik.com/v1/ai/text-to-image"


def generate_image(art_description: str, style_notes: str = "") -> Dict:
    """Generate an image using Freepik API based on art description."""
    if not FREEPIK_API_KEY:
        raise ValueError("FREEPIK_API_KEY environment variable is not set")
    
    # Build prompt from art description and style notes
    prompt = f"{art_description}"
    if style_notes:
        prompt += f", {style_notes}"
    
    # Add Game of Thrones specific styling
    prompt += ", Game of Thrones style, medieval fantasy, cinematic, detailed, atmospheric"
    
    # Negative prompt to avoid unwanted elements
    negative_prompt = "cartoon, anime, modern, colorful, bright, cheerful, b&w, black and white, earth, ugly, low quality"
    
    # Build payload matching Freepik API format exactly as per their example
    # Using simpler, validated values first
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "guidance_scale": 2,
        "seed": 42,  # Use a number instead of None
        "num_images": 1,
        "image": {"size": "square_1_1"},  # Using the example size format
        "styling": {
            "style": "digital-art",  # Try realistic first, can change to "anime" if needed
            "effects": {
                "color": "dramatic",
                "lightning": "cinematic",  # Using example value "warm" instead of "dramatic"
                "framing": "cinematic"  # Using example value "portrait" instead of "wide"
            },
            "colors": [
                {
                    "color": "#8B0000",
                    "weight": 1
                },
                {
                    "color": "#C9A961",
                    "weight": 1
                }
            ]
        },
        "filter_nsfw": True
    }
    
    headers = {
        "x-freepik-api-key": FREEPIK_API_KEY,
        "Content-Type": "application/json"
    }
    
    try:
        response = requests.post(FREEPIK_API_URL, json=payload, headers=headers, timeout=30)
        
        # Get detailed error message if request failed
        if not response.ok:
            error_detail = response.text
            try:
                error_json = response.json()
                error_detail = error_json.get('message', error_json.get('error', error_detail))
            except:
                pass
            raise Exception(f"Freepik API error ({response.status_code}): {error_detail}")
        
        return response.json()
    except requests.exceptions.RequestException as e:
        raise Exception(f"Failed to generate image: {str(e)}")

