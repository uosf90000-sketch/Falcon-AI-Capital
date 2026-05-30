import React, { useCallback } from 'react';
import { Card, FieldGroup, GameState } from '../types';
import {
  canCapture,
  executeCapture,
  executeCover,
  executeThrow,
  playerCanPlay,
  resumeTurn,
  selectCard,
  selectCoverCard,
  skipCover,
  startCover,
  endTurn,
  validTargets,
} from '../game/engine';
import { CardComponent } from './CardComponent';
import { FieldGroupCard } from './FieldGroupCard';

interface Props {
  state: GameState;
  onChange: (s: GameState) => void;
}

export function GameBoard({ state, onChange }: Props) {
  const player = state.players[state.currentPlayerIndex];
  const { turnPhase, selectedCardId, canCoverAfterAction } = state;

  // Which hand card is selected
  const selectedCard = selectedCardId
    ? player.hand.find((c) => c.id === selectedCardId) ?? null
    : null;

  // Which field groups are valid targets right now
  const highlightedGroupIds: Set<string> = (() => {
    if (turnPhase === 'select_target' && selectedCard) {
      return new Set(validTargets(selectedCard, state.field));
    }
    if (turnPhase === 'select_cover_target') {
      // Only own non-covered groups
      return new Set(
        state.field
          .filter((g) => g.ownerId === player.id && !g.topCard)
          .map((g) => g.id)
      );
    }
    return new Set<string>();
  })();

  // Which hand cards have at least one valid target
  const cardHasTargets = useCallback(
    (card: Card) => state.field.some((g) => canCapture(card, g)),
    [state.field]
  );

  const canThrow = turnPhase === 'select_target' && selectedCard &&
    validTargets(selectedCard, state.field).length === 0 &&
    !playerCanPlay(player.hand, state.field);

  // ── Handlers ──────────────────────────────────────────────────────────────

  function handleCardClick(cardId: string) {
    if (turnPhase === 'select_card') {
      onChange(selectCard(state, cardId));
    } else if (turnPhase === 'select_cover_card') {
      onChange(selectCoverCard(state, cardId));
    } else if (turnPhase === 'select_target') {
      // Re-select a different card
      onChange(selectCard(state, cardId));
    }
  }

  function handleGroupClick(groupId: string) {
    if (!highlightedGroupIds.has(groupId)) return;

    if (turnPhase === 'select_target') {
      if (canThrow) return; // throw mode, click on group has no effect
      onChange(executeCapture(state, groupId));
    } else if (turnPhase === 'select_cover_target') {
      onChange(executeCover(state, groupId));
    }
  }

  function handleThrow() {
    if (!selectedCardId) return;
    onChange(executeThrow(state, selectedCardId));
  }

  function handleEndTurn() {
    onChange(endTurn(state));
  }

  function handleCoverYes() {
    onChange(startCover(state));
  }

  function handleCoverNo() {
    onChange(skipCover(state));
    onChange(endTurn(skipCover(state)));
  }

  // Determine hand card display state
  function handCardProps(card: Card) {
    if (turnPhase === 'select_card') {
      return {
        selected: false,
        validToPlay: playerCanPlay([card], state.field),
        disabled: false,
      };
    }
    if (turnPhase === 'select_target') {
      return {
        selected: card.id === selectedCardId,
        validToPlay: false,
        disabled: false, // allow re-selection
      };
    }
    if (turnPhase === 'select_cover_card') {
      return { selected: false, validToPlay: true, disabled: false };
    }
    if (turnPhase === 'select_cover_target') {
      return {
        selected: card.id === selectedCardId,
        validToPlay: false,
        disabled: true,
      };
    }
    return { selected: false, validToPlay: false, disabled: true };
  }

  const mustThrow = turnPhase === 'select_card' && !playerCanPlay(player.hand, state.field);

  return (
    <div className="game-board">
      {/* Header */}
      <div className="game-header">
        <span className="header-title">مجابيد</span>
        <div className="header-info">
          <span className="header-chip">
            كومة السحب: <span>{state.drawPile.length}</span>
          </span>
          <span className="header-chip">
            مجموعات الميدان: <span>{state.field.length}</span>
          </span>
          <span className="current-player-badge">{player.name}</span>
        </div>
      </div>

      {/* Field */}
      <div className="field-area">
        <div className="field-label">— الميدان —</div>
        <div className="field-grid">
          {state.field.map((group) => (
            <FieldGroupCard
              key={group.id}
              group={group}
              highlighted={highlightedGroupIds.has(group.id)}
              currentPlayer={
                turnPhase === 'select_target' || turnPhase === 'select_cover_target'
                  ? player
                  : null
              }
              allPlayers={state.players}
              onClick={() => handleGroupClick(group.id)}
            />
          ))}
        </div>

        {/* Players score overview */}
        <div
          style={{
            display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center',
            marginTop: 8,
          }}
        >
          {state.players.map((p) => {
            const groupCount = state.field.filter((g) => g.ownerId === p.id).length;
            return (
              <div
                key={p.id}
                style={{
                  background: p.id === player.id ? 'rgba(241,196,15,0.15)' : 'rgba(255,255,255,0.05)',
                  border: p.id === player.id ? '1px solid rgba(241,196,15,0.4)' : '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 20,
                  padding: '3px 12px',
                  fontSize: '0.75rem',
                  color: p.id === player.id ? 'var(--gold)' : 'rgba(255,255,255,0.6)',
                }}
              >
                {p.name}: {groupCount} مجموعة · {p.hand.length} بيد
              </div>
            );
          })}
        </div>
      </div>

      {/* Action Panel */}
      <div className="action-panel">
        <div className="action-message">{state.message}</div>

        <div className="action-buttons">
          {/* Throw action */}
          {(mustThrow || canThrow) && selectedCardId && (
            <button className="btn btn-red btn-sm" onClick={handleThrow}>
              رمي الورقة في الميدان
            </button>
          )}

          {/* Must-throw with no card selected yet */}
          {mustThrow && !selectedCardId && (
            <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.85rem' }}>
              اختر أي ورقة من يدك لرميها
            </span>
          )}

          {/* Post-action: cover or end turn */}
          {turnPhase === 'post_action' && canCoverAfterAction && (
            <>
              <button className="btn btn-blue btn-sm" onClick={handleCoverYes}>
                تغطية مجموعة
              </button>
              <button className="btn btn-green btn-sm" onClick={handleCoverNo}>
                إنهاء الدور
              </button>
            </>
          )}

          {turnPhase === 'post_action' && !canCoverAfterAction && (
            <button className="btn btn-green btn-sm" onClick={handleEndTurn}>
              إنهاء الدور
            </button>
          )}

          {/* Cancel cover */}
          {(turnPhase === 'select_cover_card' || turnPhase === 'select_cover_target') && (
            <button
              className="btn btn-ghost btn-sm"
              onClick={() => onChange(endTurn(skipCover(state)))}
            >
              إلغاء التغطية وإنهاء الدور
            </button>
          )}
        </div>
      </div>

      {/* Player Hand */}
      <div className="player-hand">
        <div className="hand-label">يدك ({player.hand.length} أوراق)</div>
        <div className="hand-cards">
          {player.hand.length === 0 ? (
            <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>
              يدك فارغة
            </span>
          ) : (
            player.hand.map((card) => {
              const hp = handCardProps(card);
              return (
                <CardComponent
                  key={card.id}
                  card={card}
                  selected={hp.selected}
                  validToPlay={hp.validToPlay}
                  disabled={hp.disabled}
                  onClick={() => handleCardClick(card.id)}
                />
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}
