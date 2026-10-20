import { Level1Screen } from './level1/Level1Screen';
import { Level2Screen } from './level2/Level2Screen';
import { Level2Requirements } from './level2/Level2Requirements';
import type { LevelDefinition } from './types';

/** Add a new level by appending one entry here. The dropdown is built from this list. */
export const LEVELS: LevelDefinition[] = [
  { id: 'level-1', label: 'Level 1', Screen: Level1Screen },
  {
    id: 'level-2',
    label: 'Level 2',
    Screen: Level2Screen,
    isUnlocked: (state) => state.calculated_values_ready,
    Requirements: Level2Requirements,
  },
];

export const DEFAULT_LEVEL_ID = LEVELS[0].id;
