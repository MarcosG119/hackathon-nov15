import { useState } from 'react';
import { startGame, continueGame, generateArt, generateImage } from './api';
import type { StartGameResponse, ContinueGameResponse, GenerateArtResponse, Choice } from './types';
import './App.css';

function App() {
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [gameState, setGameState] = useState<StartGameResponse | ContinueGameResponse | null>(null);
  const [artDescription, setArtDescription] = useState<GenerateArtResponse | null>(null);
  const [sceneImage, setSceneImage] = useState<string | null>(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStartGame = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await startGame();
      setSessionId(response.session_id);
      setGameState(response);
      
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
    setSessionId(null);
    setGameState(null);
    setArtDescription(null);
    setSceneImage(null);
    setError(null);
    setImageError(null);
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
            <div className="dialogue-menu">
              <span>History</span>
              <span>Skip</span>
              <span>Auto</span>
              <span>Save</span>
              <span>Load</span>
              <span>Settings</span>
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
