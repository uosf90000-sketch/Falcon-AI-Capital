import { CardType } from '../types';

export const HIGH_TYPES: CardType[] = ['akke', 'ten', 'shayeb', 'bent', 'walad'];
export const LOW_TYPES: CardType[] = ['9', '8', '7', '6', '5', '2'];
export const ALL_TYPES: CardType[] = [...HIGH_TYPES, ...LOW_TYPES, 'joker'];

export const INITIAL_HAND_SIZE = 8;
export const DRAW_TO = 9;

export const CARD_POINTS: Record<CardType, number> = {
  akke: 10, ten: 10, shayeb: 10, bent: 10, walad: 10,
  '9': 0, '8': 0, '7': 0, '6': 0, '5': 0, '2': 0,
  joker: 50,
};

export const TYPE_COUNTS: Record<CardType, number> = {
  akke: 38, ten: 38, shayeb: 38, bent: 38, walad: 38,
  '9': 28, '8': 28, '7': 28, '6': 28, '5': 28, '2': 28,
  joker: 18,
};

// Visual colour category for cards
export type CardCategory = 'high' | 'low' | 'joker';
export const CARD_CATEGORY: Record<CardType, CardCategory> = {
  akke: 'high', ten: 'high', shayeb: 'high', bent: 'high', walad: 'high',
  '9': 'low', '8': 'low', '7': 'low', '6': 'low', '5': 'low', '2': 'low',
  joker: 'joker',
};
