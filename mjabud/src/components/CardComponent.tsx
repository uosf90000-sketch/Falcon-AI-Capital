import React from 'react';
import { Card, CARD_LABELS } from '../types';
import { CARD_CATEGORY, CARD_POINTS } from '../game/constants';

interface Props {
  card: Card;
  selected?: boolean;
  validToPlay?: boolean;
  disabled?: boolean;
  onClick?: () => void;
  size?: 'normal' | 'small';
}

export function CardComponent({ card, selected, validToPlay, disabled, onClick, size = 'normal' }: Props) {
  const category = CARD_CATEGORY[card.type];
  const points = CARD_POINTS[card.type];

  const cls = [
    size === 'small' ? 'hand-card' : 'hand-card',
    selected ? 'selected' : '',
    validToPlay && !selected ? 'valid-to-play' : '',
    disabled ? 'disabled' : '',
  ].filter(Boolean).join(' ');

  const style = size === 'small'
    ? { width: 58, height: 78 } as React.CSSProperties
    : {};

  return (
    <div className={cls} style={style} onClick={disabled ? undefined : onClick}>
      <span className={`card-label ${category}`}>
        {CARD_LABELS[card.type]}
      </span>
      {points > 0 && (
        <span className="card-points">{points} نقطة</span>
      )}
    </div>
  );
}
