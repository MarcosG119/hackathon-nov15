import os
from typing import Generator
from elevenlabs import ElevenLabs
from fastapi.responses import StreamingResponse

def generate_voice_stream(text: str, voice_id: str) -> Generator[bytes, None, None]:
    """
    Generates voice audio from text using ElevenLabs API and returns a generator of bytes.
    """
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("Error: ELEVENLABS_API_KEY is not set")
        raise ValueError("ELEVENLABS_API_KEY is not set")

    try:
        client = ElevenLabs(api_key=api_key)

        # Generates audio stream
        audio_stream = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_flash_v2_5",
            output_format="mp3_44100_128",
        )

        # Yield chunks of audio data
        for chunk in audio_stream:
            if isinstance(chunk, bytes):
                yield chunk
    except Exception as e:
        print(f"ElevenLabs API Error: {str(e)}")
        # We yield a small error message so the connection doesn't just drop, 
        # although the frontend might interpret this as a corrupt audio file.
        # Ideally, we should handle this upstream, but this helps debug server logs.
        raise e
