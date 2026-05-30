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

  const hasCover = group.topCards !== null;
  const baseCat = CARD_CATEGORY[group.baseType];

  // What's visible on top: the cover pair label OR the base type
  const topLabel = hasCover
    ? `${CARD_LABELS[group.topCards![0].type]} + ${CARD_LABELS[group.topCards![1].type]}`
    : CARD_LABELS[group.baseType];
  const topCat = hasCover ? CARD_CATEGORY[group.topCards![0].type] : baseCat;

  const groupCls = [
    'field-group',
    highlighted ? 'highlighted' : '',
    !highlighted && currentPlayer ? 'not-available' : '',
  ].filter(Boolean).join(' ');

  const cardCls = ['fg-card', isOwn ? 'owned-mine' : ''].filter(Boolean).join(' ');

  return (
    <div className={groupCls} style={{ marginTop: hasCover ? 20 : 0 }}>
      {/* Stack depth shadows */}
      {group.cards.length > 2 && (
        <div style={{
          position: 'absolute', top: hasCover ? 8 : 4,
          left: -4, right: 4, height: 120,
          background: 'rgba(255,255,255,0.6)',
          borderRadius: 8, border: '1px solid #ddd', zIndex: 0,
        }} />
      )}
      {group.cards.length > 1 && (
        <div style={{
          position: 'absolute', top: hasCover ? 4 : 2,
          left: -2, right: 2, height: 120,
          background: 'rgba(255,255,255,0.8)',
          borderRadius: 8, border: '1px solid #ddd', zIndex: 1,
        }} />
      )}

      {/* Main card face */}
      <div className={cardCls} style={{ zIndex: 2 }} onClick={onClick}>
        <span className={`fg-type-label ${topCat}`} style={{ fontSize: hasCover ? '0.85rem' : undefined }}>
          {topLabel}
        </span>

        {hasCover && (
          <span style={{
            fontSize: '0.58rem', color: '#aaa',
            borderTop: '1px dashed #ddd', paddingTop: 2, textAlign: 'center', marginTop: 2,
          }}>
            مخفي: {CARD_LABELS[group.baseType]} ({group.cards.length})
          </span>
        )}

        {!hasCover && (
          <span className="fg-count">{group.cards.length} ورقة</span>
        )}

        <span className="fg-owner" style={{ color: isOwn ? 'var(--gold)' : undefined }}>
          {isOwn ? 'أنت ✓' : ownerName}
        </span>

        {/* Expand details button */}
        {group.cards.length > 1 && (
          <button
            style={{
              position: 'absolute', bottom: 4, left: 4,
              fontSize: '0.55rem', padding: '2px 4px',
              background: 'rgba(0,0,0,0.1)', border: 'none',
              borderRadius: 4, cursor: 'pointer', color: '#666',
            }}
            onClick={(e) => { e.stopPropagation(); setShowCards(!showCards); }}
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
            zIndex: 20, minWidth: 110, boxShadow: '0 4px 12px rgba(0,0,0,0.2)',
            fontSize: '0.75rem', color: '#333', lineHeight: '1.8',
          }}
          onClick={(e) => e.stopPropagation()}
        >
          {group.cards.map((c) => (
            <div key={c.id}>{CARD_LABELS[c.type]}</div>
          ))}
          {group.topCards && (
            <div style={{ borderTop: '1px dashed #ccc', marginTop: 4, paddingTop: 4, color: '#8e44ad' }}>
              غطاء: {CARD_LABELS[group.topCards[0].type]} + {CARD_LABELS[group.topCards[1].type]}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
