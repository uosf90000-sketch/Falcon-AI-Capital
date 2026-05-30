import React, { useState } from 'react';

interface Props {
  onStart: (names: string[]) => void;
  onBack: () => void;
}

const VALID_COUNTS = [2, 4, 6, 8];

function defaultName(i: number) {
  return `لاعب ${i + 1}`;
}

export function PlayerSetup({ onStart, onBack }: Props) {
  const [count, setCount] = useState(2);
  const [names, setNames] = useState<string[]>(
    Array.from({ length: 8 }, (_, i) => defaultName(i))
  );

  const updateName = (i: number, value: string) => {
    const updated = [...names];
    updated[i] = value;
    setNames(updated);
  };

  const handleStart = () => {
    const finalNames = names.slice(0, count).map((n, i) => n.trim() || defaultName(i));
    onStart(finalNames);
  };

  return (
    <div className="screen setup-screen">
      <h2 className="setup-title">إعداد اللاعبين</h2>

      <div>
        <span className="setup-label" style={{ textAlign: 'center', display: 'block' }}>
          عدد اللاعبين
        </span>
        <div className="player-count-row" style={{ marginTop: 8 }}>
          {VALID_COUNTS.map((n) => (
            <button
              key={n}
              className={`count-btn ${count === n ? 'active' : ''}`}
              onClick={() => setCount(n)}
            >
              {n}
            </button>
          ))}
        </div>
      </div>

      <div style={{ width: '100%', maxWidth: 600 }}>
        <span className="setup-label" style={{ textAlign: 'center', display: 'block', marginBottom: 12 }}>
          أسماء اللاعبين
        </span>
        <div className="player-names-grid">
          {Array.from({ length: count }, (_, i) => (
            <div key={i} className="flex-col gap-8" style={{ alignItems: 'stretch' }}>
              <span className="setup-label">اللاعب {i + 1}</span>
              <input
                className="player-name-input"
                type="text"
                placeholder={defaultName(i)}
                value={names[i]}
                onChange={(e) => updateName(i, e.target.value)}
                maxLength={20}
              />
            </div>
          ))}
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
        <button className="btn btn-ghost" onClick={onBack}>
          رجوع
        </button>
        <button className="btn btn-gold btn-lg" onClick={handleStart}>
          ابدأ اللعبة ←
        </button>
      </div>

      <div style={{ color: 'rgba(255,255,255,0.3)', fontSize: '0.8rem', textAlign: 'center' }}>
        إجمالي الأوراق: ٣٧٦ ورقة &nbsp;|&nbsp; يحصل كل لاعب على ٨ أوراق في البداية
      </div>
    </div>
  );
}
