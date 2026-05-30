import React from 'react';
import { GameState, ScoreEntry } from '../types';
import { computeScores } from '../game/engine';
import { CARD_LABELS } from '../types';
import { CARD_POINTS } from '../game/constants';

interface Props {
  state: GameState;
  onRestart: () => void;
}

export function ResultsScreen({ state, onRestart }: Props) {
  const scores: ScoreEntry[] = computeScores(state)
    .sort((a, b) => b.score - a.score);

  const winner = scores[0];
  const isTie = scores.length > 1 && scores[0].score === scores[1].score;

  const arabicRank = ['الأول', 'الثاني', 'الثالث', 'الرابع', 'الخامس', 'السادس', 'السابع', 'الثامن'];

  return (
    <div className="screen results-screen">
      <h1 className="results-title">نتائج اللعبة</h1>

      {/* Winner banner */}
      <div className="results-winner">
        {isTie ? (
          <>
            <div className="winner-label">🤝 تعادل بين</div>
            <div className="winner-name">
              {scores.filter(s => s.score === winner.score).map(s => s.player.name).join(' و ')}
            </div>
          </>
        ) : (
          <>
            <div className="winner-label">🏆 الفائز</div>
            <div className="winner-name">{winner.player.name}</div>
          </>
        )}
        <div className="winner-score">{winner.score} نقطة</div>
      </div>

      {/* Score table */}
      <table className="scores-table">
        <thead>
          <tr>
            <th>المركز</th>
            <th>اللاعب</th>
            <th>مجموعات</th>
            <th>أوراق عالية</th>
            <th>جوكر</th>
            <th>المجموع</th>
          </tr>
        </thead>
        <tbody>
          {scores.map((entry, rank) => {
            const highCards = entry.groupCards.filter(c =>
              ['akke','ten','shayeb','bent','walad'].includes(c.type)
            ).length + entry.capturedCards.filter(c =>
              ['akke','ten','shayeb','bent','walad'].includes(c.type)
            ).length;
            const jokers = entry.groupCards.filter(c => c.type === 'joker').length +
              entry.capturedCards.filter(c => c.type === 'joker').length;

            return (
              <tr key={entry.player.id} className={rank === 0 && !isTie ? 'is-winner' : ''}>
                <td>
                  <span className={`rank-badge ${rank === 0 && !isTie ? 'first' : ''}`}>
                    {arabicRank[rank] ?? rank + 1}
                  </span>
                </td>
                <td>{entry.player.name}</td>
                <td>{entry.ownedGroups.length}</td>
                <td>{highCards} × ١٠</td>
                <td>{jokers} × ٥٠</td>
                <td style={{ fontWeight: 700 }}>{entry.score}</td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Field groups summary */}
      <details style={{ width: '100%', maxWidth: 540 }}>
        <summary
          style={{
            cursor: 'pointer', color: 'rgba(255,255,255,0.6)',
            fontSize: '0.85rem', textAlign: 'center', listStyle: 'none',
            padding: '8px 0',
          }}
        >
          عرض تفاصيل مجموعات الميدان
        </summary>
        <div
          style={{
            background: 'rgba(0,0,0,0.2)', borderRadius: 8,
            padding: 12, marginTop: 8,
            display: 'flex', flexWrap: 'wrap', gap: 8,
          }}
        >
          {state.field.map((g) => {
            const owner = state.players.find(p => p.id === g.ownerId);
            const pts = g.cards.reduce((s, c) => s + (CARD_POINTS[c.type] ?? 0), 0)
              + (g.topCards ? g.topCards.reduce((s, c) => s + (CARD_POINTS[c.type] ?? 0), 0) : 0);
            return (
              <div
                key={g.id}
                style={{
                  background: 'rgba(255,255,255,0.07)',
                  borderRadius: 6, padding: '6px 10px',
                  fontSize: '0.8rem', color: 'rgba(255,255,255,0.7)',
                  minWidth: 130,
                }}
              >
                <div style={{ fontWeight: 700, color: '#fff' }}>
                  {CARD_LABELS[g.baseType]} ({g.cards.length})
                </div>
                <div>{owner ? owner.name : 'بلا مالك'}</div>
                <div style={{ color: 'var(--gold)' }}>{pts} نقطة</div>
                {g.topCards && (
                  <div style={{ color: '#8e44ad', fontSize: '0.7rem' }}>
                    غطاء: {CARD_LABELS[g.topCards[0].type]} + {CARD_LABELS[g.topCards[1].type]}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </details>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center', marginTop: 8 }}>
        <button className="btn btn-gold btn-lg" onClick={onRestart}>
          لعبة جديدة
        </button>
      </div>
    </div>
  );
}
