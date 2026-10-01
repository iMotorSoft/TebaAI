import { describe, expect, it } from 'vitest';
import { sourceTextRuns } from './sourceTextRuns';

describe('source numeric equation isolation', () => {
  it('keeps cells isolated when API folds the original table rows', () => {
    const text = 'GUEMATRIA 300 = ש ; 6 = ו ; 1 = א 400 = ת ; 80 = פ,ף ; 30 = ל';
    const runs = sourceTextRuns(text);
    expect(runs.join('')).toBe(text);
    for (const cell of ['300 = ש', '6 = ו', '1 = א', '400 = ת', '80 = פ,ף', '30 = ל']) {
      expect(runs).toContain(cell);
    }
  });
  it('keeps Hebrew vowel marks attached to their equation letter', () => {
    const text = '1 = אַ ; 2 = בּ';
    expect(sourceTextRuns(text)).toEqual(['1 = אַ', ' ; ', '2 = בּ']);
  });
  it.each(['שלום עולם, ו1 y ת80.', 'English; Spanish 1,25!', '6 = ו 1 = א', 'Referencia 6 = ו ; texto', 'שלום; עולם'])('preserves unstructured text: %s', text => {
    expect(sourceTextRuns(text)).toEqual([text]);
  });
});
