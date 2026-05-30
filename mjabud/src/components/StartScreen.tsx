import React from 'react';
import { CARD_LABELS } from '../types';

interface Props {
  onStart: () => void;
}

const PREVIEW: Array<{ label: string; cls: string }> = [
  { label: CARD_LABELS['akke'], cls: 'high' },
  { label: CARD_LABELS['walad'], cls: 'high' },
  { label: CARD_LABELS['joker'], cls: 'joker' },
  { label: CARD_LABELS['bent'], cls: 'high' },
  { label: CARD_LABELS['5'], cls: 'low' },
];

export function StartScreen({ onStart }: Props) {
  return (
    <div className="screen start-screen">
      <h1 className="start-title">مجابيد</h1>

      <div className="start-cards-preview">
        {PREVIEW.map((c, i) => (
          <div key={i} className="mini-card">
            <span className={`card-label ${c.cls}`}>{c.label}</span>
          </div>
        ))}
      </div>

      <p className="start-subtitle">
        لعبة ورق استراتيجية — استولِ على المجموعات، غطِّها لحمايتها،
        واجمع أعلى النقاط للفوز!
      </p>

      <button className="btn btn-gold btn-lg" onClick={onStart}>
        ابدأ اللعبة
      </button>

      <div style={{ marginTop: 16, color: 'rgba(255,255,255,0.35)', fontSize: '0.8rem', textAlign: 'center' }}>
        ٢ · ٤ · ٦ · ٨ لاعبين &nbsp;|&nbsp; محلي أو شبكي
      </div>
    </div>
  );
}
