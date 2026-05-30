import { Card, CardType } from '../types';
import { ALL_TYPES, TYPE_COUNTS } from './constants';

let _counter = 0;

export function createDeck(): Card[] {
  _counter = 0;
  const deck: Card[] = [];
  for (const type of ALL_TYPES) {
    for (let i = 0; i < TYPE_COUNTS[type as CardType]; i++) {
      deck.push({ id: `c${_counter++}`, type: type as CardType });
    }
  }
  return deck;
}

export function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}
