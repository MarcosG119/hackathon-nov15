import { StartGameResponse, ContinueGameResponse, GenerateArtResponse, GenerateImageResponse } from './types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function startGame(): Promise<StartGameResponse> {
  const response = await fetch(`${API_BASE_URL}/api/game/start`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({}),
  });

  if (!response.ok) {
    throw new Error(`Failed to start game: ${response.statusText}`);
  }

  return response.json();
}

export async function continueGame(sessionId: string, choiceId: string): Promise<ContinueGameResponse> {
  const response = await fetch(`${API_BASE_URL}/api/game/continue`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      choice_id: choiceId,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to continue game: ${response.statusText}`);
  }

  return response.json();
}

export async function generateArt(sessionId: string, sceneSetting: string, currNarrative: string): Promise<GenerateArtResponse> {
  const response = await fetch(`${API_BASE_URL}/api/game/generate-art`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      session_id: sessionId,
      scene_setting: sceneSetting,
      curr_narrative: currNarrative,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to generate art: ${response.statusText}`);
  }

  return response.json();
}

export async function generateImage(artDescription: string, styleNotes: string = ''): Promise<GenerateImageResponse> {
  const response = await fetch(`${API_BASE_URL}/api/game/generate-image`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      art_description: artDescription,
      style_notes: styleNotes,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to generate image: ${response.statusText}`);
  }

  return response.json();
}

export async function generateVoice(text: string, voiceId: string): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}/api/game/generate-voice`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      text: text,
      voice_id: voiceId,
    }),
  });

  if (!response.ok) {
    throw new Error(`Failed to generate voice: ${response.statusText}`);
  }

  return response.blob();
}
