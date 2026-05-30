import { Card, CardType, FieldGroup, GameState, Player, ScoreEntry, TurnPhase } from '../types';
import { ALL_TYPES, CARD_POINTS, DRAW_TO, INITIAL_HAND_SIZE } from './constants';
import { createDeck, shuffle } from './deck';

// ─── Helpers ───────────────────────────────────────────────────────────────

function clone<T>(v: T): T {
  return JSON.parse(JSON.stringify(v));
}

let _gid = 0;
function nextGroupId(): string {
  return `g${++_gid}`;
}

// ─── Initialisation ────────────────────────────────────────────────────────

export function initGame(playerNames: string[], aiFlags: boolean[] = []): GameState {
  _gid = 0;
  const deck = shuffle(createDeck());
  let idx = 0;

  const players: Player[] = playerNames.map((name, i) => ({
    id: `p${i}`,
    name,
    isAI: aiFlags[i] ?? false,
    hand: deck.slice(idx + i * INITIAL_HAND_SIZE, idx + (i + 1) * INITIAL_HAND_SIZE),
    capturedPile: [],
  }));
  idx += playerNames.length * INITIAL_HAND_SIZE;

  // One card of every type goes to the field as a starter group
  const field: FieldGroup[] = ALL_TYPES.map((type) => ({
    id: nextGroupId(),
    baseType: type as CardType,
    cards: [deck[idx++]],
    ownerId: null,
    topCard: null,
  }));

  return {
    phase: 'playing',
    players,
    field,
    drawPile: deck.slice(idx),
    currentPlayerIndex: 0,
    selectedCardId: null,
    turnPhase: 'select_card',
    lastCapturedGroupId: null,
    message: buildStartMessage(playerNames[0]),
    canCoverAfterAction: false,
  };
}

function buildStartMessage(name: string): string {
  return `دور اللاعب: ${name}`;
}

// ─── Capture logic ─────────────────────────────────────────────────────────

/**
 * Can `card` be played on `group`?
 * - If group has a topCard → must match topCard type (or be Joker).
 * - Otherwise → must match group baseType (or be Joker).
 */
export function canCapture(card: Card, group: FieldGroup): boolean {
  if (card.type === 'joker') return true;
  const target = group.topCard ?? null;
  if (target) return card.type === target.type;
  return card.type === group.baseType;
}

export function validTargets(card: Card, field: FieldGroup[]): string[] {
  return field.filter((g) => canCapture(card, g)).map((g) => g.id);
}

export function playerCanPlay(hand: Card[], field: FieldGroup[]): boolean {
  return hand.some((c) => field.some((g) => canCapture(c, g)));
}

// ─── Turn actions ──────────────────────────────────────────────────────────

export function selectCard(state: GameState, cardId: string): GameState {
  const s = clone(state);
  const player = s.players[s.currentPlayerIndex];
  if (!player.hand.find((c: Card) => c.id === cardId)) return state;

  s.selectedCardId = cardId;
  s.turnPhase = 'select_target' as TurnPhase;

  const card = player.hand.find((c: Card) => c.id === cardId)!;
  const targets = validTargets(card, s.field);

  if (targets.length === 0 && !playerCanPlay(player.hand, s.field)) {
    // No valid targets with any card → must throw
    s.turnPhase = 'select_target' as TurnPhase;
    s.message = 'لا يمكنك أخذ أي مجموعة. ستُرمى هذه الورقة في الميدان.';
  } else if (targets.length === 0) {
    // Selected card has no targets, but other cards might
    s.selectedCardId = null;
    s.turnPhase = 'select_card' as TurnPhase;
    s.message = 'هذه الورقة لا تستطيع أخذ أي مجموعة. اختر ورقة أخرى.';
  } else {
    s.message = 'اختر المجموعة التي تريد أخذها.';
  }

  return s;
}

export function executeCapture(state: GameState, groupId: string): GameState {
  const s = clone(state);
  const player = s.players[s.currentPlayerIndex];
  const cardId = s.selectedCardId!;
  const cardIdx = player.hand.findIndex((c: Card) => c.id === cardId);
  const playedCard: Card = player.hand.splice(cardIdx, 1)[0];
  const group = s.field.find((g: FieldGroup) => g.id === groupId)!;

  if (group.topCard) {
    // Capturing the cover card — both go to capturedPile
    player.capturedPile.push(playedCard, group.topCard);
    group.topCard = null;
    s.lastCapturedGroupId = null;
    s.canCoverAfterAction = false;
    s.message = 'أخذت الورقة العليا! المجموعة أصبحت مكشوفة.';
  } else {
    // Capturing the group itself
    group.cards.push(playedCard);
    group.ownerId = player.id;
    s.lastCapturedGroupId = groupId;
    s.canCoverAfterAction = true;
    s.message = `استوليت على مجموعة! هل تريد تغطية إحدى مجموعاتك؟`;
  }

  s.selectedCardId = null;
  s.turnPhase = 'post_action' as TurnPhase;
  return s;
}

export function executeThrow(state: GameState, cardId: string): GameState {
  const s = clone(state);
  const player = s.players[s.currentPlayerIndex];
  const cardIdx = player.hand.findIndex((c: Card) => c.id === cardId);
  const thrown: Card = player.hand.splice(cardIdx, 1)[0];

  s.field.push({
    id: nextGroupId(),
    baseType: thrown.type,
    cards: [thrown],
    ownerId: null,
    topCard: null,
  });

  s.selectedCardId = null;
  s.turnPhase = 'post_action' as TurnPhase;
  s.canCoverAfterAction = false;
  s.lastCapturedGroupId = null;
  s.message = 'رميت ورقة في الميدان.';
  return s;
}

export function startCover(state: GameState): GameState {
  const s = clone(state);
  s.turnPhase = 'select_cover_card' as TurnPhase;
  s.message = 'اختر ورقة من يدك لتغطية إحدى مجموعاتك.';
  return s;
}

export function selectCoverCard(state: GameState, cardId: string): GameState {
  const s = clone(state);
  s.selectedCardId = cardId;
  s.turnPhase = 'select_cover_target' as TurnPhase;
  s.message = 'اختر المجموعة التي تريد تغطيتها.';
  return s;
}

export function executeCover(state: GameState, groupId: string): GameState {
  const s = clone(state);
  const player = s.players[s.currentPlayerIndex];
  const cardId = s.selectedCardId!;
  const cardIdx = player.hand.findIndex((c: Card) => c.id === cardId);
  const coverCard: Card = player.hand.splice(cardIdx, 1)[0];
  const group = s.field.find((g: FieldGroup) => g.id === groupId)!;

  group.topCard = coverCard;
  s.selectedCardId = null;
  s.turnPhase = 'post_action' as TurnPhase;
  s.canCoverAfterAction = false;
  s.message = 'غطيت المجموعة! انتهى دورك.';
  return s;
}

export function skipCover(state: GameState): GameState {
  const s = clone(state);
  s.canCoverAfterAction = false;
  s.turnPhase = 'post_action' as TurnPhase;
  s.message = 'انتهى دورك.';
  return s;
}

// ─── End of turn ──────────────────────────────────────────────────────────

export function endTurn(state: GameState): GameState {
  let s = clone(state);
  const player = s.players[s.currentPlayerIndex];

  // Draw cards until DRAW_TO (if draw pile available)
  while (player.hand.length < DRAW_TO && s.drawPile.length > 0) {
    player.hand.push(s.drawPile.pop()!);
  }

  s.lastCapturedGroupId = null;
  s.canCoverAfterAction = false;
  s.selectedCardId = null;

  if (isGameOver(s)) {
    s.phase = 'ended';
    s.message = 'انتهت اللعبة!';
    return s;
  }

  // Advance to the next player who still has cards; skip empty hands.
  const n = s.players.length;
  let next = (s.currentPlayerIndex + 1) % n;
  let checked = 0;
  while (s.players[next].hand.length === 0 && checked < n) {
    next = (next + 1) % n;
    checked++;
  }

  // If every remaining player has an empty hand the game is over
  if (s.players[next].hand.length === 0) {
    s.phase = 'ended';
    s.message = 'انتهت اللعبة!';
    return s;
  }

  s.currentPlayerIndex = next;
  s.phase = 'pass_device';
  s.turnPhase = 'select_card' as TurnPhase;
  s.message = '';
  return s;
}

export function resumeTurn(state: GameState): GameState {
  const s = clone(state);
  s.phase = 'playing';
  const player = s.players[s.currentPlayerIndex];

  if (player.hand.length === 0) {
    // Should not normally happen (endTurn skips empty-hand players), but guard anyway
    s.message = 'يدك فارغة — الدور ينتقل تلقائياً.';
  } else if (!playerCanPlay(player.hand, s.field)) {
    s.message = `لا يمكنك أخذ أي مجموعة. يجب عليك رمي ورقة.`;
    s.turnPhase = 'select_card' as TurnPhase;
  } else {
    s.message = `دور اللاعب: ${player.name}`;
    s.turnPhase = 'select_card' as TurnPhase;
  }
  return s;
}

// ─── Game over ────────────────────────────────────────────────────────────

export function isGameOver(state: GameState): boolean {
  return (
    state.drawPile.length === 0 &&
    state.players.every((p: Player) => p.hand.length === 0)
  );
}

// ─── Scoring ─────────────────────────────────────────────────────────────

export function computeScores(state: GameState): ScoreEntry[] {
  return state.players.map((player: Player) => {
    const ownedGroups = state.field.filter(
      (g: FieldGroup) => g.ownerId === player.id
    );

    const groupCards: Card[] = [];
    for (const g of ownedGroups) {
      groupCards.push(...g.cards);
      // topCard still on the group at game end also counts for group owner
      if (g.topCard) groupCards.push(g.topCard);
    }

    const allCards = [...groupCards, ...player.capturedPile];
    const score = allCards.reduce(
      (sum: number, c: Card) => sum + (CARD_POINTS[c.type] ?? 0),
      0
    );

    return {
      player,
      ownedGroups,
      groupCards,
      capturedCards: player.capturedPile,
      score,
    };
  });
}
