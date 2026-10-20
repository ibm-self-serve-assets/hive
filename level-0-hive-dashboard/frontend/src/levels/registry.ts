import { Level1Screen } from './level1/Level1Screen';
import type { LevelDefinition } from './types';

/** Add a new level by appending one entry here. The dropdown is built from this list. */
export const LEVELS: LevelDefinition[] = [
  { id: 'level-1', label: 'Level 1', Screen: Level1Screen },
];

export const DEFAULT_LEVEL_ID = LEVELS[0].id;
