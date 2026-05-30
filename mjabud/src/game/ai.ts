import { Card, FieldGroup, GameState } from '../types';
import { CARD_POINTS } from './constants';
import {
  canCapture,
  executeCapture,
  executeCover,
  executeThrow,
  endTurn,
  skipCover,
} from './engine';

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

/** Total point value of all cards in a field group (base cards + topCard) */
function groupValue(group: FieldGroup): number {
  const cardSum = group.cards.reduce((sum, c) => sum + (CARD_POINTS[c.type] ?? 0), 0);
  const topSum = group.topCard ? (CARD_POINTS[group.topCard.type] ?? 0) : 0;
  return cardSum + topSum;
}

/**
 * Find the best (card, group) capture pair.
 * Priority: maximise points captured from the group.
 * Among equal group values, prefer playing a lower-value card (save high-value for later).
 * Jokers are used only when no other option captures a given group.
 */
function findBestCapture(
  hand: Card[],
  field: FieldGroup[]
): { card: Card; group: FieldGroup } | null {
  let best: { card: Card; group: FieldGroup; groupVal: number; cardVal: number } | null = null;

  for (const card of hand) {
    for (const group of field) {
      if (!canCapture(card, group)) continue;
      const groupVal = groupValue(group);
      const cardVal = CARD_POINTS[card.type] ?? 0;

      if (!best) {
        best = { card, group, groupVal, cardVal };
        continue;
      }

      // Prefer higher-value group
      if (groupVal > best.groupVal) {
        best = { card, group, groupVal, cardVal };
        continue;
      }
      if (groupVal < best.groupVal) continue;

      // Same group value: prefer lower-value card (don't waste high cards)
      if (cardVal < best.cardVal) {
        best = { card, group, groupVal, cardVal };
        continue;
      }
      // Same card value: prefer non-joker cards
      if (card.type !== 'joker' && best.card.type === 'joker') {
        best = { card, group, groupVal, cardVal };
      }
    }
  }

  return best ? { card: best.card, group: best.group } : null;
}

/**
 * After capturing, decide whether to cover a high-value owned group
 * with a zero-point card.
 * Conditions:
 *  - canCoverAfterAction must be true
 *  - There exists an owned, uncovered group with total value >= 30
 *  - There is a zero-point card in hand (prefer non-joker zero cards)
 */
function findCoverMove(state: GameState): { coverCardId: string; groupId: string } | null {
  if (!state.canCoverAfterAction) return null;

  const player = state.players[state.currentPlayerIndex];

  // Find the highest-value owned uncovered group with value >= 30
  const ownedHighGroups = state.field
    .filter((g) => g.ownerId === player.id && !g.topCard && groupValue(g) >= 30)
    .sort((a, b) => groupValue(b) - groupValue(a));

  if (ownedHighGroups.length === 0) return null;

  // Find a zero-point card in hand (prefer non-joker)
  const zeroPtCards = player.hand.filter((c) => (CARD_POINTS[c.type] ?? 0) === 0 && c.type !== 'joker');
  const coverCard = zeroPtCards.length > 0
    ? zeroPtCards[0]
    : null; // don't use joker to cover

  if (!coverCard) return null;

  return { coverCardId: coverCard.id, groupId: ownedHighGroups[0].id };
}

/**
 * Choose the best card to throw when no capture is possible.
 * Strategy: throw lowest-value card, avoiding jokers if any other card exists.
 */
function findThrowCard(hand: Card[]): Card {
  // Prefer non-joker cards; among those, pick the one with lowest point value
  const nonJokers = hand.filter((c) => c.type !== 'joker');
  const pool = nonJokers.length > 0 ? nonJokers : hand;
  return pool.reduce((worst, c) =>
    (CARD_POINTS[c.type] ?? 0) <= (CARD_POINTS[worst.type] ?? 0) ? c : worst
  );
}

/**
 * Execute a full AI turn and return state ready for `endTurn`.
 * This is a pure function — it clones state before mutating.
 */
export function executeAITurn(state: GameState): GameState {
  let s: GameState = clone(state);

  const player = s.players[s.currentPlayerIndex];
  const capture = findBestCapture(player.hand, s.field);

  if (capture) {
    // Set selectedCardId then execute capture
    s.selectedCardId = capture.card.id;
    s = executeCapture(s, capture.group.id);

    // Decide whether to cover after capture
    const coverMove = findCoverMove(s);
    if (coverMove) {
      s.selectedCardId = coverMove.coverCardId;
      s = executeCover(s, coverMove.groupId);
    } else {
      s = skipCover(s);
    }
  } else {
    // No valid capture — throw lowest-value card
    const throwCard = findThrowCard(player.hand);
    s = executeThrow(s, throwCard.id);
  }

  return s;
}
