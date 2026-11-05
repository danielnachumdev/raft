/** Log the real error; return a short UI message with no backend detail. */
export function userFacingError(err: unknown, fallback: string): string {
  if (err instanceof Error) console.error(err);
  return fallback;
}
