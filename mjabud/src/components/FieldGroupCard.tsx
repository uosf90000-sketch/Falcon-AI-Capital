import React, { useState } from 'react';
import { FieldGroup as FG, CARD_LABELS, Player } from '../types';
import { CARD_CATEGORY } from '../game/constants';

interface Props {
  group: FG;
  highlighted: boolean;
  currentPlayer: Player | null;
  allPlayers: Player[];
  onClick: () => void;
}

export function FieldGroupCard({ group, highlighted, currentPlayer, allPlayers, onClick }: Props) {
  const [showCards, setShowCards] = useState(false);

  const isOwn = currentPlayer && group.ownerId === currentPlayer.id;
  const ownerName = group.ownerId
    ? allPlayers.find(p => p.id === group.ownerId)?.name ?? 'لاعب'
    : 'ميدان';
  const hasTop = group.topCard !== null;

  const baseCat = CARD_CATEGORY[group.baseType];
  const topCat = hasTop ? CARD_CATEGORY[group.topCard!.type] : null;

  const cardCls = [
    'fg-card',
    isOwn ? 'owned-mine' : '',
  ].filter(Boolean).join(' ');

  const groupCls = [
    'field-group',
    highlighted ? 'highlighted' : '',
    !highlighted && currentPlayer ? 'not-available' : '',
  ].filter(Boolean).join(' ');

  // The visible entity is the topCard if it exists, else the base group
  const topLabel = hasTop ? CARD_LABELS[group.topCard!.type] : CARD_LABELS[group.baseType];
  const topCatClass = hasTop ? topCat : baseCat;

  return (
    <div className={groupCls} style={{ marginTop: hasTop ? 20 : 0 }}>
      {/* Stack depth shadow layers */}
      {group.cards.length > 2 && (
        <div
          style={{
            position: 'absolute', top: hasTop ? 8 : 4,
            left: -4, right: 4,
            height: 120, background: 'rgba(255,255,255,0.6)',
            borderRadius: 8, border: '1px solid #ddd', zIndex: 0,
          }}
        />
      )}
      {group.cards.length > 1 && (
        <div
          style={{
            position: 'absolute', top: hasTop ? 4 : 2,
            left: -2, right: 2,
            height: 120, background: 'rgba(255,255,255,0.8)',
            borderRadius: 8, border: '1px solid #ddd', zIndex: 1,
          }}
        />
      )}

      {/* Main visible card */}
      <div className={cardCls} style={{ zIndex: 2 }} onClick={onClick}>
        <span className={`fg-type-label ${topCatClass}`}>{topLabel}</span>
        {hasTop && (
          <span
            style={{
              fontSize: '0.6rem',
              color: '#aaa',
              marginTop: 2,
              borderTop: '1px dashed #ddd',
              paddingTop: 2,
              textAlign: 'center',
            }}
          >
            فوق: {CARD_LABELS[group.baseType]}
          </span>
        )}
        <span className="fg-count">{group.cards.length} ورقة</span>
        <span className="fg-owner" style={{ color: isOwn ? 'var(--gold)' : undefined }}>
          {isOwn ? 'أنت ✓' : ownerName}
        </span>

        {/* Expand cards detail */}
        {group.cards.length > 1 && (
          <button
            style={{
              position: 'absolute', bottom: 4, left: 4,
              fontSize: '0.55rem', padding: '2px 4px',
              background: 'rgba(0,0,0,0.1)', border: 'none',
              borderRadius: 4, cursor: 'pointer', color: '#666',
            }}
            onClick={(e) => { e.stopPropagation(); setShowCards(!showCards); }}
            title="عرض الأوراق"
          >
            {showCards ? '▲' : '▼'}
          </button>
        )}
      </div>

      {/* Expanded card list */}
      {showCards && (
        <div
          style={{
            position: 'absolute', top: 128, right: 0,
            background: '#fff', border: '1px solid #ddd',
            borderRadius: 6, padding: '6px 8px',
            zIndex: 20, minWidth: 100, boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            fontSize: '0.75rem', color: '#333', lineHeight: '1.8',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {group.cards.map((c) => (
            <div key={c.id}>{CARD_LABELS[c.type]}</div>
          ))}
          {group.topCard && (
            <div style={{ borderTop: '1px dashed #ccc', marginTop: 4, paddingTop: 4, color: '#8e44ad' }}>
              غطاء: {CARD_LABELS[group.topCard.type]}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
