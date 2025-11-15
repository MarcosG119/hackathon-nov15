export interface Choice {
  id: string;
  description: string;
  risk_level: string;
}

export interface Character {
  name: string;
  trust_level: number;
  threat_level: string;
}

export interface StartGameResponse {
  session_id: string;
  scene_setting: string;
  narrative: string;
  choices: Choice[];
  characters: Character[];
  game_status: string;
}

export interface ContinueGameResponse {
  narrative: string;
  scene_setting: string;
  scene_changed: boolean;
  choices: Choice[];
  characters: Character[];
  game_status: string;
  game_over: boolean;
  victory: boolean;
}

export interface GenerateArtResponse {
  art_description: string;
  style_notes: string;
}

export interface GenerateImageResponse {
  image_url?: string;
  error?: string;
}

