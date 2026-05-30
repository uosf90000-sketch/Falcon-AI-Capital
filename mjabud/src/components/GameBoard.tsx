import React, { useCallback, useEffect } from 'react';
import { Card, FieldGroup, GameState } from '../types';
import {
  canCapture,
  canPlaceCover,
  executeCapture,
  executeCoverPair,
  executeThrow,
  playerCanPlay,
  selectCard,
  selectCoverCard1,
  selectCoverCard2,
  skipCover,
  startCover,
  endTurn,
  validTargets,
} from '../game/engine';
import { executeAITurn } from '../game/ai';
import { CardComponent } from './CardComponent';
import { FieldGroupCard } from './FieldGroupCard';
import { CARD_LABELS } from '../types';

interface Props {
  state: GameState;
  onChange: (s: GameState) => void;
}

export function GameBoard({ state, onChange }: Props) {
  const player = state.players[state.currentPlayerIndex];
  const { turnPhase, selectedCardId, pendingCoverCardId, canCoverAfterAction } = state;

  // AI auto-play
  useEffect(() => {
    if (!player.isAI || turnPhase !== 'select_card') return;
    const timer = setTimeout(() => {
      onChange(endTurn(executeAITurn(state)));
    }, 1200);
    return () => clearTimeout(timer);
  }, [player.id, player.isAI, turnPhase]); // eslint-disable-line react-hooks/exhaustive-deps

  // Selected cards
  const selectedCard = selectedCardId
    ? player.hand.find((c) => c.id === selectedCardId) ?? null
    : null;
  const pendingCoverCard = pendingCoverCardId
    ? player.hand.find((c) => c.id === pendingCoverCardId) ?? null
    : null;

  // Which field groups are valid targets
  const highlightedGroupIds: Set<string> = (() => {
    if (turnPhase === 'select_target' && selectedCard) {
      return new Set(validTargets(selectedCard, state.field));
    }
    if (turnPhase === 'select_cover_target') {
      return new Set(
        state.field
          .filter((g) => g.ownerId === player.id && !g.topCards)
          .map((g) => g.id)
      );
    }
    return new Set<string>();
  })();

  const canThrow =
    turnPhase === 'select_target' &&
    selectedCard &&
    validTargets(selectedCard, state.field).length === 0 &&
    !playerCanPlay(player.hand, state.field);

  const mustThrow =
    turnPhase === 'select_card' && !playerCanPlay(player.hand, state.field);

  // ── Handlers ──────────────────────────────────────────────────────────────

  function handleCardClick(cardId: string) {
    if (turnPhase === 'select_card' || turnPhase === 'select_target') {
      onChange(selectCard(state, cardId));
    } else if (turnPhase === 'select_cover_card_1') {
      onChange(selectCoverCard1(state, cardId));
    } else if (turnPhase === 'select_cover_card_2') {
      // Second card must match first card's type (or both jokers)
      const first = player.hand.find((c) => c.id === pendingCoverCardId)!;
      const second = player.hand.find((c) => c.id === cardId)!;
      if (cardId === pendingCoverCardId) return; // can't pick same card
      if (second.type !== first.type) {
        onChange({ ...state, message: `الورقة الثانية يجب أن تكون ${CARD_LABELS[first.type]} أيضاً.` });
        return;
      }
      onChange(selectCoverCard2(state, cardId));
    }
  }

  function handleGroupClick(groupId: string) {
    if (!highlightedGroupIds.has(groupId)) return;
    if (turnPhase === 'select_target') {
      if (canThrow) return;
      onChange(executeCapture(state, groupId));
    } else if (turnPhase === 'select_cover_target') {
      onChange(executeCoverPair(state, groupId));
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
    onChange(endTurn(skipCover(state)));
  }

  // Hand card display state
  function handCardProps(card: Card) {
    if (turnPhase === 'select_card') {
      return { selected: false, validToPlay: playerCanPlay([card], state.field), disabled: false };
    }
    if (turnPhase === 'select_target') {
      return { selected: card.id === selectedCardId, validToPlay: false, disabled: false };
    }
    if (turnPhase === 'select_cover_card_1') {
      // Highlight cards that have a matching pair in hand
      const sameType = player.hand.filter((c) => c.type === card.type);
      return { selected: false, validToPlay: sameType.length >= 2, disabled: false };
    }
    if (turnPhase === 'select_cover_card_2') {
      const first = player.hand.find((c) => c.id === pendingCoverCardId);
      const isMatch = first && card.type === first.type && card.id !== pendingCoverCardId;
      return {
        selected: card.id === pendingCoverCardId,
        validToPlay: !!isMatch,
        disabled: !isMatch && card.id !== pendingCoverCardId,
      };
    }
    if (turnPhase === 'select_cover_target') {
      return { selected: card.id === selectedCardId || card.id === pendingCoverCardId, validToPlay: false, disabled: true };
    }
    return { selected: false, validToPlay: false, disabled: true };
  }

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
            الميدان: <span>{state.field.length}</span>
          </span>
          <span className="current-player-badge">
            {player.isAI ? '🤖 ' : ''}{player.name}
          </span>
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

        {/* Players overview */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, justifyContent: 'center', marginTop: 8 }}>
          {state.players.map((p) => {
            const groupCount = state.field.filter((g) => g.ownerId === p.id).length;
            return (
              <div key={p.id} style={{
                background: p.id === player.id ? 'rgba(241,196,15,0.15)' : 'rgba(255,255,255,0.05)',
                border: p.id === player.id ? '1px solid rgba(241,196,15,0.4)' : '1px solid rgba(255,255,255,0.1)',
                borderRadius: 20, padding: '3px 12px',
                fontSize: '0.75rem',
                color: p.id === player.id ? 'var(--gold)' : 'rgba(255,255,255,0.6)',
              }}>
                {p.isAI ? '🤖' : '👤'} {p.name}: {groupCount} مجموعة · {p.hand.length} بيد
              </div>
            );
          })}
        </div>
      </div>

      {/* Action Panel */}
      <div className="action-panel">
        <div className="action-message">{state.message}</div>

        {player.isAI && turnPhase === 'select_card' && (
          <div style={{ textAlign: 'center', color: 'var(--gold)', fontSize: '1rem', marginBottom: 4 }}>
            🤖 يفكر...
          </div>
        )}

        {/* Cover step 2 hint */}
        {turnPhase === 'select_cover_card_2' && pendingCoverCard && (
          <div style={{ textAlign: 'center', fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)', marginBottom: 4 }}>
            اخترت: <strong style={{ color: 'var(--gold)' }}>{CARD_LABELS[pendingCoverCard.type]}</strong> — اختر ورقة ثانية من نفس النوع
          </div>
        )}

        <div className="action-buttons">
          {/* Throw */}
          {(mustThrow || canThrow) && selectedCardId && (
            <button className="btn btn-red btn-sm" onClick={handleThrow}>رمي الورقة في الميدان</button>
          )}
          {mustThrow && !selectedCardId && (
            <span style={{ color: 'rgba(255,255,255,0.6)', fontSize: '0.85rem' }}>اختر أي ورقة من يدك لرميها</span>
          )}

          {/* Post-action: cover or end */}
          {turnPhase === 'post_action' && canCoverAfterAction && (
            <>
              <button className="btn btn-blue btn-sm" onClick={handleCoverYes}>تغطية بورقتين</button>
              <button className="btn btn-green btn-sm" onClick={handleCoverNo}>إنهاء الدور</button>
            </>
          )}
          {turnPhase === 'post_action' && !canCoverAfterAction && (
            <button className="btn btn-green btn-sm" onClick={handleEndTurn}>إنهاء الدور</button>
          )}

          {/* Cancel cover */}
          {(turnPhase === 'select_cover_card_1' || turnPhase === 'select_cover_card_2' || turnPhase === 'select_cover_target') && (
            <button className="btn btn-ghost btn-sm" onClick={() => onChange(endTurn(skipCover(state)))}>
              إلغاء وإنهاء الدور
            </button>
          )}
        </div>
      </div>

      {/* Player Hand */}
      <div className="player-hand">
        <div className="hand-label">
          يدك ({player.hand.length} أوراق)
          {turnPhase === 'select_cover_card_1' && ' — اختر الورقة الأولى للغطاء'}
          {turnPhase === 'select_cover_card_2' && ' — اختر الورقة الثانية المطابقة'}
        </div>
        <div className="hand-cards">
          {player.hand.length === 0 ? (
            <span style={{ color: 'rgba(255,255,255,0.4)', fontSize: '0.85rem' }}>يدك فارغة</span>
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
