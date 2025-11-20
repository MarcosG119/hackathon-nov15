import { useState, useEffect, useRef } from 'react';
import { startGame, continueGame, generateArt, generateImage, generateVoice } from './api';
import type { StartGameResponse, ContinueGameResponse, GenerateArtResponse, Choice } from './types';
import './App.css';

// voice ID (can be changed)
const VOICE_ID = "2ajXGJNYBR0iNHpS4VZb";

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<StartGameResponse | ContinueGameResponse | null>(null);
  const [artDescription, setArtDescription] = useState<GenerateArtResponse | null>(null);
  const [sceneImage, setSceneImage] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  
  // Ref to keep track of the current voice audio
  const currentVoiceRef = useRef<HTMLAudioElement | null>(null);

  useEffect(() => {
    const audio = new Audio('/music.mp3');
    audio.loop = true;
    audio.volume = 0.1;
    
    const playAudio = async () => {
      try {
        await audio.play();
      } catch (err) {
        console.log("Autoplay prevented, waiting for interaction:", err);
        const handleInteraction = () => {
          audio.play();
          document.removeEventListener('click', handleInteraction);
          document.removeEventListener('keydown', handleInteraction);
        };
        document.addEventListener('click', handleInteraction);
        document.addEventListener('keydown', handleInteraction);
      }
    };

    playAudio();

    return () => {
      audio.pause();
      audio.currentTime = 0;
    };
  }, []);

  const playVoiceOver = async (text: string) => {
    if (isMuted) return;
    
    try {
      console.log("Generating voice for:", text);
      // Stop any currently playing voice
      if (currentVoiceRef.current) {
        currentVoiceRef.current.pause();
        currentVoiceRef.current = null;
      }

      const audioBlob = await generateVoice(text, VOICE_ID);
      console.log("Voice blob received size:", audioBlob.size);
      
      if (audioBlob.size < 100) {
        console.warn("Received unusually small audio blob, might be an error response.");
        return;
      }
      
      const audioUrl = URL.createObjectURL(audioBlob);
      const audio = new Audio(audioUrl);
      
      audio.onerror = (e) => console.error("Audio playback error:", e);
      audio.onplay = () => console.log("Audio started playing");
      
      currentVoiceRef.current = audio;
      await audio.play();
      
      // Cleanup URL after playback
      audio.onended = () => {
        console.log("Audio playback finished");
        URL.revokeObjectURL(audioUrl);
        if (currentVoiceRef.current === audio) {
          currentVoiceRef.current = null;
        }
      };
    } catch (err) {
      console.error("Failed to play voice over:", err);
    }
  };

  const handleStartGame = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await startGame();
      setSessionId(response.session_id);
      setGameState(response);
      
      // Start voice over for initial narrative
      playVoiceOver(response.narrative);
      
      // Generate art for initial scene
      const art = await generateArt(response.session_id, response.scene_setting, response.narrative);
      setArtDescription(art);
      
      // Generate image for the scene
      setImageLoading(true);
      setImageError(null);
      try {
        const imageResult = await generateImage(art.art_description, art.style_notes);
        if (imageResult.image_url) {
          setSceneImage(imageResult.image_url);
        } else if (imageResult.error) {
          setImageError(imageResult.error);
        }
      } catch (err) {
        setImageError(err instanceof Error ? err.message : 'Failed to generate image');
      } finally {
        setImageLoading(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start game');
    } finally {
      setLoading(false);
    }
  };

  const handleChoice = async (choice: Choice) => {
    if (!sessionId) return;
    
    setLoading(true);
    setError(null);
    try {
      const response = await continueGame(sessionId, choice.id);
      setGameState(response);
      
      // Start voice over for new narrative
      playVoiceOver(response.narrative);
      
      // Generate art if scene changed
      if (response.scene_changed) {
        const art = await generateArt(sessionId, response.scene_setting, response.narrative);
        setArtDescription(art);
        
        // Generate image for the new scene
        setImageLoading(true);
        setImageError(null);
        try {
          const imageResult = await generateImage(art.art_description, art.style_notes);
          if (imageResult.image_url) {
            setSceneImage(imageResult.image_url);
          } else if (imageResult.error) {
            setImageError(imageResult.error);
          }
        } catch (err) {
          setImageError(err instanceof Error ? err.message : 'Failed to generate image');
        } finally {
          setImageLoading(false);
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to continue game');
    } finally {
      setLoading(false);
    }
  };

  const handleNewGame = () => {
    // Stop any playing voice
    if (currentVoiceRef.current) {
      currentVoiceRef.current.pause();
      currentVoiceRef.current = null;
    }
    setSessionId(null);
    setGameState(null);
    setArtDescription(null);
    setSceneImage(null);
    setError(null);
    setImageError(null);
  };

  const toggleMute = () => {
    setIsMuted(prev => {
      const newState = !prev;
      if (newState && currentVoiceRef.current) {
        currentVoiceRef.current.pause();
      }
      return newState;
    });
  };

  if (!gameState) {
    return (
      <div className="app-container">
        <div className="start-screen">
          <h1 className="game-title">Escape King's Landing</h1>
          <p className="game-subtitle">A Visual Novel Adventure</p>
          <div className="game-description">
            <p>You are Ned Stark, Hand of the King. Robert Baratheon is dead, and the Lannisters are closing in.</p>
            <p>Your honor demands action, but your survival depends on escaping this city alive.</p>
            <p>Choose wisely. The game of thrones is unforgiving.</p>
          </div>
          {error && <div className="error-message">{error}</div>}
          <button 
            className="start-button" 
            onClick={handleStartGame}
            disabled={loading}
          >
            {loading ? 'Starting...' : 'Begin Your Escape'}
          </button>
        </div>
      </div>
    );
  }

  const isGameOver = 'game_over' in gameState && gameState.game_over;
  const isVictory = 'victory' in gameState && gameState.victory;

  return (
    <div className="app-container">
      {/* Full-screen background image */}
      <div className="scene-background">
        {sceneImage ? (
          <img 
            src={sceneImage} 
            alt={gameState.scene_setting}
            className="scene-image-fullscreen"
            onError={() => setImageError('Failed to load image')}
          />
        ) : (
          <div className="scene-image-placeholder">
            {imageLoading ? (
              <>
                <div className="loading-spinner"></div>
                <p>Generating scene...</p>
              </>
            ) : (
              <div className="no-image-placeholder">
                <p>Scene image will appear here</p>
              </div>
            )}
          </div>
        )}
        
        {imageError && (
          <div className="image-error-overlay">
            Image generation unavailable: {imageError}
          </div>
        )}
      </div>

      {/* Overlay UI Elements */}
      <div className="game-overlay">
        {/* Top menu bar */}
        <div className="top-menu-bar">
          <button className="menu-button" onClick={handleNewGame}>
            New Game
          </button>
          <button className="menu-button" onClick={toggleMute}>
            {isMuted ? '🔇 Unmute Voice' : '🔊 Mute Voice'}
          </button>
        </div>

        {/* Choices - positioned center-right */}
        {!isGameOver && gameState.choices && gameState.choices.length > 0 && (
          <div className="choices-overlay">
            {gameState.choices.map((choice) => (
              <button
                key={choice.id}
                className="choice-box"
                onClick={() => handleChoice(choice)}
                disabled={loading}
              >
                {choice.description}
              </button>
            ))}
          </div>
        )}

        {/* Dialogue box at bottom */}
        <div className="dialogue-overlay">
          <div className="dialogue-box">
            <div className="dialogue-text">
              {gameState.narrative}
            </div>
          </div>
        </div>

        {/* Game Over Screen */}
        {isGameOver && (
          <div className={`game-over-overlay ${isVictory ? 'victory' : 'defeat'}`}>
            <div className="game-over-content">
              <h2>{isVictory ? '🏆 Victory!' : '💀 Defeat'}</h2>
              <p className="game-over-message">
                {isVictory 
                  ? 'You have escaped King\'s Landing! Your honor and survival are preserved.' 
                  : 'The game of thrones has claimed another victim. Your honor could not save you.'}
              </p>
              <button className="restart-button" onClick={handleNewGame}>
                Play Again
              </button>
            </div>
          </div>
        )}

        {/* Loading Indicator */}
        {loading && (
          <div className="loading-overlay">
            <div className="loading-spinner"></div>
            <p>Thinking...</p>
          </div>
        )}

        {/* Error Message */}
        {error && (
          <div className="error-overlay">
            <div className="error-message">{error}</div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
