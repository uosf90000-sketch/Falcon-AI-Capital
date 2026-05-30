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
    topCards: null,
  }));

  return {
    phase: 'playing',
    players,
    field,
    drawPile: deck.slice(idx),
    currentPlayerIndex: 0,
    selectedCardId: null,
    pendingCoverCardId: null,
    turnPhase: 'select_card',
    lastCapturedGroupId: null,
    message: `دور اللاعب: ${playerNames[0]}`,
    canCoverAfterAction: false,
  };
}

// ─── Capture logic ─────────────────────────────────────────────────────────

/**
 * Can `card` be played on `group`?
 * - If group has a cover pair → card must match topCards[0].type (or be Joker).
 * - Otherwise → card must match group baseType (or be Joker).
 */
export function canCapture(card: Card, group: FieldGroup): boolean {
  if (card.type === 'joker') return true;
  if (group.topCards) return card.type === group.topCards[0].type;
  return card.type === group.baseType;
}

export function validTargets(card: Card, field: FieldGroup[]): string[] {
  return field.filter((g) => canCapture(card, g)).map((g) => g.id);
}

export function playerCanPlay(hand: Card[], field: FieldGroup[]): boolean {
  return hand.some((c) => field.some((g) => canCapture(c, g)));
}

// Returns true if player has at least 2 cards of the same type (for cover)
export function canPlaceCover(hand: Card[]): boolean {
  const counts: Partial<Record<string, number>> = {};
  for (const c of hand) {
    counts[c.type] = (counts[c.type] ?? 0) + 1;
    if (counts[c.type]! >= 2) return true;
  }
  return false;
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
    s.message = 'لا يمكنك أخذ أي مجموعة. ستُرمى هذه الورقة في الميدان.';
  } else if (targets.length === 0) {
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

  if (group.topCards) {
    // Capturing the cover pair — played card + both cover cards → capturedPile
    player.capturedPile.push(playedCard, ...group.topCards);
    group.topCards = null;
    s.lastCapturedGroupId = null;
    s.canCoverAfterAction = false;
    s.message = 'أخذت الغطاء! المجموعة أصبحت مكشوفة.';
  } else {
    // Capturing the group itself — played card added, player takes ownership
    group.cards.push(playedCard);
    group.ownerId = player.id;
    s.lastCapturedGroupId = groupId;
    // Cover allowed only if player has ≥2 cards of same type remaining
    s.canCoverAfterAction = canPlaceCover(player.hand);
    s.message = s.canCoverAfterAction
      ? 'استوليت على المجموعة! هل تريد تغطيتها بورقتين؟'
      : 'استوليت على المجموعة!';
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
    topCards: null,
  });

  s.selectedCardId = null;
  s.pendingCoverCardId = null;
  s.turnPhase = 'post_action' as TurnPhase;
  s.canCoverAfterAction = false;
  s.lastCapturedGroupId = null;
  s.message = 'رميت ورقة في الميدان.';
  return s;
}

// Cover step 1: start the cover flow
export function startCover(state: GameState): GameState {
  const s = clone(state);
  s.turnPhase = 'select_cover_card_1' as TurnPhase;
  s.pendingCoverCardId = null;
  s.message = 'اختر الورقة الأولى للغطاء.';
  return s;
}

// Cover step 2: player picked first card, now pick a matching second card
export function selectCoverCard1(state: GameState, cardId: string): GameState {
  const s = clone(state);
  s.pendingCoverCardId = cardId;
  s.turnPhase = 'select_cover_card_2' as TurnPhase;
  const card = s.players[s.currentPlayerIndex].hand.find((c: Card) => c.id === cardId)!;
  s.message = `اخترت ${card.type === 'joker' ? 'جوكر' : card.type}. الآن اختر ورقة ثانية من نفس النوع.`;
  return s;
}

// Cover step 3: player picked second card (must match first), now pick target group
export function selectCoverCard2(state: GameState, cardId: string): GameState {
  const s = clone(state);
  s.selectedCardId = cardId;
  s.turnPhase = 'select_cover_target' as TurnPhase;
  s.message = 'اختر المجموعة التي تريد تغطيتها.';
  return s;
}

// Cover step 4: apply the cover pair on the chosen group
export function executeCoverPair(state: GameState, groupId: string): GameState {
  const s = clone(state);
  const player = s.players[s.currentPlayerIndex];

  const card1Id = s.pendingCoverCardId!;
  const card2Id = s.selectedCardId!;

  const idx1 = player.hand.findIndex((c: Card) => c.id === card1Id);
  const card1: Card = player.hand.splice(idx1, 1)[0];

  // After splicing card1, re-find card2 index
  const idx2 = player.hand.findIndex((c: Card) => c.id === card2Id);
  const card2: Card = player.hand.splice(idx2, 1)[0];

  const group = s.field.find((g: FieldGroup) => g.id === groupId)!;
  group.topCards = [card1, card2];

  s.selectedCardId = null;
  s.pendingCoverCardId = null;
  s.turnPhase = 'post_action' as TurnPhase;
  s.canCoverAfterAction = false;
  s.message = 'وضعت الغطاء! المجموعة محمية.';
  return s;
}

export function skipCover(state: GameState): GameState {
  const s = clone(state);
  s.canCoverAfterAction = false;
  s.pendingCoverCardId = null;
  s.selectedCardId = null;
  s.turnPhase = 'post_action' as TurnPhase;
  s.message = 'انتهى دورك.';
  return s;
}

// ─── End of turn ──────────────────────────────────────────────────────────

export function endTurn(state: GameState): GameState {
  const s = clone(state);
  const player = s.players[s.currentPlayerIndex];

  // Draw cards until DRAW_TO (if draw pile available)
  while (player.hand.length < DRAW_TO && s.drawPile.length > 0) {
    player.hand.push(s.drawPile.pop()!);
  }

  s.lastCapturedGroupId = null;
  s.canCoverAfterAction = false;
  s.selectedCardId = null;
  s.pendingCoverCardId = null;

  if (isGameOver(s)) {
    s.phase = 'ended';
    s.message = 'انتهت اللعبة!';
    return s;
  }

  // Advance to next player with cards; skip empty hands
  const n = s.players.length;
  let next = (s.currentPlayerIndex + 1) % n;
  let checked = 0;
  while (s.players[next].hand.length === 0 && checked < n) {
    next = (next + 1) % n;
    checked++;
  }

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
    s.message = 'يدك فارغة — الدور ينتقل تلقائياً.';
  } else if (!playerCanPlay(player.hand, s.field)) {
    s.message = 'لا يمكنك أخذ أي مجموعة. يجب عليك رمي ورقة.';
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
      // topCards still on the group at game end count for the group owner
      if (g.topCards) groupCards.push(...g.topCards);
    }

    const allCards = [...groupCards, ...player.capturedPile];
    const score = allCards.reduce(
      (sum: number, c: Card) => sum + (CARD_POINTS[c.type] ?? 0),
      0
    );

    return { player, ownedGroups, groupCards, capturedCards: player.capturedPile, score };
  });
}
