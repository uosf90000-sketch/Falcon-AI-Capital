import React from 'react';

interface Props {
  playerName: string;
  onReady: () => void;
}

export function PassDevice({ playerName, onReady }: Props) {
  return (
    <div className="screen pass-screen" onClick={onReady}>
      <div style={{ fontSize: '3rem' }}>🎴</div>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '1rem', color: 'rgba(255,255,255,0.5)', marginBottom: 8 }}>
          مرر الجهاز إلى
        </div>
        <div className="pass-player-name">{playerName}</div>
      </div>
      <p className="pass-instruction">
        اضغط في أي مكان عندما يكون الجهاز بيدك
      </p>
      <button className="btn btn-gold" style={{ marginTop: 8 }} onClick={onReady}>
        أنا جاهز — ابدأ دوري
      </button>
    </div>
  );
}
