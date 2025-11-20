import os
import json
import uuid
import base64
import requests
import logging
from typing import Dict, Optional, List, Tuple
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import numpy as np
from openai import OpenAI

# Configure logger for image caching
logger = logging.getLogger("image_cache")
logger.setLevel(logging.INFO)

# Create console handler if it doesn't exist
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Try to load .env file from multiple possible locations
# 1. Project root (for Docker: /app/../.env, for local: ./fastApiServer/../.env)
project_root = Path(__file__).parent.parent.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)

# 2. Current directory (for local development)
load_dotenv(override=False)

# Constants
SIMILARITY_THRESHOLD = 0.85  # Threshold for cache hit (tune this value)
FREEPIK_API_KEY = os.getenv("FREEPIK_API_KEY")
FREEPIK_API_URL = "https://api.freepik.com/v1/ai/text-to-image"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Initialize OpenAI client for embeddings
if OPENAI_API_KEY:
    openai_client = OpenAI(api_key=OPENAI_API_KEY)
else:
    openai_client = None

# Cache directory and metadata file paths
CACHE_DIR = project_root / "image_cache"
METADATA_FILE = project_root / "cache_metadata.json"

# Ensure cache directory exists
CACHE_DIR.mkdir(exist_ok=True)


def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    vec1_array = np.array(vec1)
    vec2_array = np.array(vec2)
    
    dot_product = np.dot(vec1_array, vec2_array)
    norm1 = np.linalg.norm(vec1_array)
    norm2 = np.linalg.norm(vec2_array)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))


def get_embedding(text: str) -> List[float]:
    """Get embedding vector for text using OpenAI API."""
    if not openai_client:
        raise ValueError("OPENAI_API_KEY environment variable is not set")
    
    try:
        response = openai_client.embeddings.create(
            model="text-embedding-3-small",
            input=text
        )
        return response.data[0].embedding
    except Exception as e:
        raise Exception(f"Failed to get embedding: {str(e)}")


def load_cache_metadata() -> List[Dict]:
    """Load cache metadata from JSON file."""
    if not METADATA_FILE.exists():
        logger.debug("Cache metadata file does not exist, starting with empty cache")
        return []
    
    try:
        with open(METADATA_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Ensure it's a list
            if isinstance(data, list):
                logger.info(f"Loaded {len(data)} entries from cache metadata")
                return data
            else:
                logger.warning("Cache metadata is not a list, returning empty cache")
                return []
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Failed to load cache metadata: {e}")
        return []


def save_cache_metadata(metadata: List[Dict]):
    """Save cache metadata to JSON file."""
    try:
        with open(METADATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
        logger.debug(f"Saved {len(metadata)} entries to cache metadata")
    except IOError as e:
        logger.error(f"Failed to save cache metadata: {e}")


def search_cache(query_embedding: List[float], cache_metadata: List[Dict]) -> Tuple[Optional[Dict], float]:
    """Search cache for similar images using cosine similarity.
    
    Returns:
        Tuple of (best_match_dict, max_similarity_score)
    """
    max_similarity = 0.0
    best_match = None
    
    logger.info(f"Searching cache with {len(cache_metadata)} entries...")
    
    for cached_item in cache_metadata:
        cached_embedding = cached_item.get("embedding")
        if not cached_embedding:
            logger.warning(f"Cache entry missing embedding: {cached_item.get('id', 'unknown')}")
            continue
        
        similarity = cosine_similarity(query_embedding, cached_embedding)
        text_preview = cached_item.get('text', '')[:60].replace('\n', ' ')
        logger.info(f"  Similarity: {similarity:.4f} | Text: '{text_preview}...'")
        
        if similarity > max_similarity:
            max_similarity = similarity
            best_match = cached_item
    
    return best_match, max_similarity


def save_image_to_cache(base64_data: str, image_id: str) -> Path:
    """Save base64 image data to cache directory.
    
    Returns:
        Path to saved image file
    """
    # Remove data URL prefix if present
    if base64_data.startswith("data:image"):
        base64_data = base64_data.split(",")[1]
    
    image_path = CACHE_DIR / f"img_{image_id}.png"
    
    try:
        image_bytes = base64.b64decode(base64_data)
        with open(image_path, 'wb') as f:
            f.write(image_bytes)
        return image_path
    except Exception as e:
        raise Exception(f"Failed to save image to cache: {str(e)}")


def load_image_from_cache(image_path: Path) -> str:
    """Load image from cache and convert to data URL.
    
    Returns:
        Data URL string (data:image/png;base64,...)
    """
    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
            base64_data = base64.b64encode(image_bytes).decode('utf-8')
            return f"data:image/png;base64,{base64_data}"
    except Exception as e:
        raise Exception(f"Failed to load image from cache: {str(e)}")


def verify_cache_entry(cached_item: Dict) -> bool:
    """Verify that a cache entry's image file still exists."""
    image_path = project_root / cached_item.get("image_path", "")
    return image_path.exists()


def generate_image(art_description: str, style_notes: str = "") -> Dict:
    """Generate an image using Freepik API based on art description.
    
    This is the low-level function that actually calls the API.
    Use generate_image_with_cache() for cached generation.
    """
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
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "guidance_scale": 2,
        "seed": 42,
        "num_images": 1,
        "image": {"size": "square_1_1"},
        "styling": {
            "style": "digital-art",
            "effects": {
                "color": "dramatic",
                "lightning": "cinematic",
                "framing": "cinematic"
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


def generate_image_with_cache(art_description: str, style_notes: str = "") -> Dict:
    """Generate an image with intelligent semantic caching.
    
    This function:
    1. Gets embedding for the scene description
    2. Searches cache for semantically similar images
    3. Returns cached image if similarity >= threshold
    4. Otherwise generates new image and caches it
    
    Returns:
        Dict with 'image_url' (data URL) and optionally 'cached' boolean
    """
    # Combine description and style notes for semantic search
    search_text = f"{art_description}"
    if style_notes:
        search_text += f" {style_notes}"
    
    # Step 1: Get embedding for the query
    logger.info("=" * 60)
    logger.info("IMAGE CACHE CHECK")
    logger.info("=" * 60)
    logger.info(f"Query text: '{search_text[:150]}...'")
    
    try:
        logger.info("Getting embedding from OpenAI...")
        query_embedding = get_embedding(search_text)
        logger.info(f"Embedding received (dimension: {len(query_embedding)})")
    except Exception as e:
        logger.error(f"Failed to get embedding, generating without cache: {e}")
        # Fallback to direct generation
        result = generate_image(art_description, style_notes)
        return _extract_image_url_from_result(result)
    
    # Step 2: Load cache metadata
    cache_metadata = load_cache_metadata()
    
    # Step 3: Search cache
    best_match, max_similarity = search_cache(query_embedding, cache_metadata)
    
    logger.info(f"Max similarity found: {max_similarity:.4f} (threshold: {SIMILARITY_THRESHOLD})")
    
    # Step 4: Decision - Cache HIT
    if best_match and max_similarity >= SIMILARITY_THRESHOLD:
        # Verify the image file still exists
        if verify_cache_entry(best_match):
            image_path = project_root / best_match["image_path"]
            logger.info(f"[CACHE HIT] Score: {max_similarity:.4f}")
            logger.info(f"   Reusing image: {best_match['image_path']}")
            logger.info(f"   Matched text: '{best_match.get('text', '')[:100]}...'")
            
            try:
                image_url = load_image_from_cache(image_path)
                logger.info("   Image loaded successfully from cache")
                return {
                    "image_url": image_url,
                    "cached": True
                }
            except Exception as e:
                logger.warning(f"Failed to load cached image, generating new one: {e}")
                # Fall through to generate new image
        else:
            logger.warning(f"Cached image file missing: {best_match['image_path']}, generating new one")
            # Remove invalid entry from cache
            cache_metadata = [item for item in cache_metadata if item.get("id") != best_match.get("id")]
            save_cache_metadata(cache_metadata)
    
    # Step 5: Cache MISS - Generate new image
    logger.info(f"[CACHE MISS] Max Score: {max_similarity:.4f}")
    logger.info("Generating new image via Freepik API...")
    
    try:
        result = generate_image(art_description, style_notes)
        image_url = _extract_image_url_from_result(result)
        
        if not image_url:
            raise Exception("Failed to extract image URL from API response")
        
        # Step 6: Save to cache
        image_id = str(uuid.uuid4())
        
        # Extract base64 data from data URL
        base64_data = image_url
        if image_url.startswith("data:image"):
            base64_data = image_url.split(",")[1]
        
        # Save image to disk
        image_path = save_image_to_cache(base64_data, image_id)
        relative_path = image_path.relative_to(project_root)
        
        # Create metadata entry
        new_entry = {
            "id": image_id,
            "text": search_text,
            "embedding": query_embedding,
            "image_path": str(relative_path),
            "timestamp": datetime.now().isoformat()
        }
        
        # Append to cache metadata
        cache_metadata.append(new_entry)
        save_cache_metadata(cache_metadata)
        
        logger.info(f"[SUCCESS] New image generated and saved to cache: {relative_path}")
        logger.info(f"   Cache now contains {len(cache_metadata)} entries")
        
        return {
            "image_url": image_url,
            "cached": False
        }
        
    except Exception as e:
        logger.error(f"Error generating image: {e}", exc_info=True)
        raise


def _extract_image_url_from_result(result: Dict) -> Optional[str]:
    """Extract image URL from Freepik API response."""
    image_url = None
    if isinstance(result, dict):
        # Check for base64 image data (Freepik API format)
        if "data" in result and isinstance(result["data"], list) and len(result["data"]) > 0:
            first_image = result["data"][0]
            if "base64" in first_image:
                # Convert base64 to data URL for frontend display
                base64_data = first_image["base64"]
                image_url = f"data:image/jpeg;base64,{base64_data}"
            elif "url" in first_image:
                image_url = first_image["url"]
            elif "image_url" in first_image:
                image_url = first_image["image_url"]
        # Fallback to other possible formats
        elif "url" in result:
            image_url = result["url"]
        elif "image_url" in result:
            image_url = result["image_url"]
        elif "images" in result and isinstance(result["images"], list) and len(result["images"]) > 0:
            image_url = result["images"][0].get("url") or result["images"][0].get("image_url")
    
    return image_url
