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
  topCard: Card | null; // covering card placed over the group
}

export interface Player {
  id: string;
  name: string;
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
  | 'select_card'         // player picks a card from hand
  | 'select_target'       // player picks a field group to act on
  | 'post_action'         // action done; player may choose to cover
  | 'select_cover_card'   // player picks a card to use as cover
  | 'select_cover_target';// player picks which of their groups to cover

export interface GameState {
  phase: GamePhase;
  players: Player[];
  field: FieldGroup[];
  drawPile: Card[];
  currentPlayerIndex: number;
  selectedCardId: string | null;
  turnPhase: TurnPhase;
  lastCapturedGroupId: string | null; // group captured this turn (can be covered)
  message: string;
  canCoverAfterAction: boolean;       // whether covering is allowed this turn
}

export interface ScoreEntry {
  player: Player;
  ownedGroups: FieldGroup[];
  groupCards: Card[];
  capturedCards: Card[];
  score: number;
}
