// Card types using internal identifiers
export type CardType =
  | 'akke'    // أكّه
  | 'ten'     // ١٠
  | 'shayeb'  // شايب
  | 'bent'    // بنت
  | 'walad'   // ولد
  | '9' | '8' | '7' | '6' | '5' | '2'
  | 'joker';  // جوكر

export const CARD_LABELS: Record<CardType, string> = {
  akke: 'أكّه',
  ten: '١٠',
  shayeb: 'شايب',
  bent: 'بنت',
  walad: 'ولد',
  '9': '٩',
  '8': '٨',
  '7': '٧',
  '6': '٦',
  '5': '٥',
  '2': '٢',
  joker: 'جوكر',
};

export interface Card {
  id: string;
  type: CardType;
}

// A group of cards on the field
export interface FieldGroup {
  id: string;
  baseType: CardType;   // determines what can capture it when uncovered
  cards: Card[];        // all accumulated cards (for scoring)
  ownerId: string | null;
  // Cover is always a PAIR of two same-type cards placed on top
  topCards: [Card, Card] | null;
}

export interface Player {
  id: string;
  name: string;
  isAI: boolean;
  hand: Card[];
  capturedPile: Card[]; // individual cards captured from cover-captures
}

// Phases of the whole game
export type GamePhase =
  | 'start'
  | 'setup'
  | 'playing'
  | 'pass_device'
  | 'ended';

// Phases within a single player's turn
export type TurnPhase =
  | 'select_card'           // choose a card from hand
  | 'select_target'         // choose where to play the card
  | 'post_action'           // action done; player may choose to cover
  | 'select_cover_card_1'   // choose FIRST card of the cover pair
  | 'select_cover_card_2'   // choose SECOND card (must match first)
  | 'select_cover_target';  // choose which own group to cover

export interface GameState {
  phase: GamePhase;
  players: Player[];
  field: FieldGroup[];
  drawPile: Card[];
  currentPlayerIndex: number;
  selectedCardId: string | null;
  pendingCoverCardId: string | null; // first cover card (waiting for second)
  turnPhase: TurnPhase;
  lastCapturedGroupId: string | null;
  message: string;
  canCoverAfterAction: boolean;
}

export interface ScoreEntry {
  player: Player;
  ownedGroups: FieldGroup[];
  groupCards: Card[];
  capturedCards: Card[];
  score: number;
}
