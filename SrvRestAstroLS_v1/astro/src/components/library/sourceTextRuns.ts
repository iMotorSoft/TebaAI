/** Isolate equation cells in source text that already has explicit table delimiters.
 * The runs concatenate byte-for-byte to the source; no text is normalized.
 */
export function sourceTextRuns(text: string): string[] {
  const cells = [...text.matchAll(/[0-9]+\s*=\s*[\u05d0-\u05ea]\p{M}*(?:\s*,\s*[\u05d0-\u05ea]\p{M}*)?/gu)];
  if (!text.includes(" ; ") || cells.length < 2) return [text];
  const runs: string[] = [];
  let offset = 0;
  for (const cell of cells) {
    if (cell.index! > offset) runs.push(text.slice(offset, cell.index));
    runs.push(cell[0]);
    offset = cell.index! + cell[0].length;
  }
  if (offset < text.length) runs.push(text.slice(offset));
  return runs;
}
