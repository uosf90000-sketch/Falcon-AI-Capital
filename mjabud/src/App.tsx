import React, { useState } from 'react';
import { GameState } from './types';
import { initGame, resumeTurn } from './game/engine';
import { StartScreen } from './components/StartScreen';
import { PlayerSetup } from './components/PlayerSetup';
import { PassDevice } from './components/PassDevice';
import { GameBoard } from './components/GameBoard';
import { ResultsScreen } from './components/ResultsScreen';
import './styles/global.css';

type AppPhase = 'start' | 'setup' | 'game' | 'pass' | 'ended';

export default function App() {
  const [appPhase, setAppPhase] = useState<AppPhase>('start');
  const [game, setGame] = useState<GameState | null>(null);

  function handleStart() {
    setAppPhase('setup');
  }

  function handleSetup(playerNames: string[]) {
    const state = initGame(playerNames);
    setGame(state);
    setAppPhase('game');
  }

  function handleGameChange(newState: GameState) {
    if (newState.phase === 'ended') {
      setGame(newState);
      setAppPhase('ended');
    } else if (newState.phase === 'pass_device') {
      setGame(newState);
      setAppPhase('pass');
    } else {
      setGame(newState);
    }
  }

  function handlePassReady() {
    if (!game) return;
    const resumed = resumeTurn(game);
    setGame(resumed);
    setAppPhase('game');
  }

  function handleRestart() {
    setGame(null);
    setAppPhase('start');
  }

  if (appPhase === 'start') {
    return <StartScreen onStart={handleStart} />;
  }

  if (appPhase === 'setup') {
    return <PlayerSetup onStart={handleSetup} onBack={() => setAppPhase('start')} />;
  }

  if (appPhase === 'pass' && game) {
    const nextPlayer = game.players[game.currentPlayerIndex];
    return <PassDevice playerName={nextPlayer.name} onReady={handlePassReady} />;
  }

  if (appPhase === 'game' && game) {
    return <GameBoard state={game} onChange={handleGameChange} />;
  }

  if (appPhase === 'ended' && game) {
    return <ResultsScreen state={game} onRestart={handleRestart} />;
  }

  return null;
}
