import { Card, FieldGroup, GameState } from '../types';
import { CARD_POINTS } from './constants';
import { canCapture, canPlaceCover } from './engine';

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

function groupValue(group: FieldGroup): number {
  return group.cards.reduce((s, c) => s + (CARD_POINTS[c.type] ?? 0), 0);
}

function coverValue(group: FieldGroup): number {
  if (!group.topCards) return 0;
  return group.topCards.reduce((s, c) => s + (CARD_POINTS[c.type] ?? 0), 0);
}

export function executeAITurn(state: GameState): GameState {
  const s = clone(state) as GameState;
  const player = s.players[s.currentPlayerIndex];

  // ── Find best capture ──────────────────────────────────────────────────
  let bestCardId: string | null = null;
  let bestGroupId: string | null = null;
  let bestScore = -1;

  for (const card of player.hand) {
    for (const group of s.field) {
      if (!canCapture(card, group)) continue;
      const score = group.topCards
        ? coverValue(group) + (CARD_POINTS[card.type] ?? 0)
        : groupValue(group) + (CARD_POINTS[card.type] ?? 0);
      if (score > bestScore) {
        bestScore = score;
        bestCardId = card.id;
        bestGroupId = group.id;
      }
    }
  }

  if (bestCardId && bestGroupId) {
    const cardIdx = player.hand.findIndex((c) => c.id === bestCardId);
    const playedCard = player.hand.splice(cardIdx, 1)[0];
    const group = s.field.find((g) => g.id === bestGroupId)!;

    if (group.topCards) {
      // Capture cover pair
      player.capturedPile.push(playedCard, ...group.topCards);
      group.topCards = null;
    } else {
      // Capture group
      group.cards.push(playedCard);
      group.ownerId = player.id;

      // Optionally cover most valuable own group with a low-value pair
      if (canPlaceCover(player.hand)) {
        const myGroups = s.field.filter((g) => g.ownerId === player.id && !g.topCards);
        const target = myGroups
          .filter((g) => groupValue(g) >= 20)
          .sort((a, b) => groupValue(b) - groupValue(a))[0];

        if (target) {
          // Find two same-type cards with lowest point value
          const typeBuckets: Record<string, Card[]> = {};
          for (const c of player.hand) {
            if (!typeBuckets[c.type]) typeBuckets[c.type] = [];
            typeBuckets[c.type].push(c);
          }
          const pair = Object.values(typeBuckets)
            .filter((arr) => arr.length >= 2)
            .sort((a, b) => (CARD_POINTS[a[0].type] ?? 0) - (CARD_POINTS[b[0].type] ?? 0))[0];

          if (pair) {
            const [c1, c2] = pair;
            player.hand.splice(player.hand.findIndex((c) => c.id === c1.id), 1);
            player.hand.splice(player.hand.findIndex((c) => c.id === c2.id), 1);
            target.topCards = [c1, c2];
          }
        }
      }
    }
  } else {
    // Can't capture — throw lowest-value non-joker card
    const throwCard = player.hand
      .filter((c) => c.type !== 'joker')
      .sort((a, b) => (CARD_POINTS[a.type] ?? 0) - (CARD_POINTS[b.type] ?? 0))[0]
      ?? player.hand[0];

    const throwIdx = player.hand.findIndex((c) => c.id === throwCard.id);
    player.hand.splice(throwIdx, 1);
    s.field.push({
      id: `g_ai_${Date.now()}`,
      baseType: throwCard.type,
      cards: [throwCard],
      ownerId: null,
      topCards: null,
    });
  }

  s.canCoverAfterAction = false;
  s.selectedCardId = null;
  s.pendingCoverCardId = null;
  return s;
}
