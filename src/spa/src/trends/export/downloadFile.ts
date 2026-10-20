/** Trigger a browser download from text or a Blob. */

export function downloadTextFile(
  text: string,
  filename: string,
  mediaType: string,
): void {
  downloadBlob(new Blob([text], { type: mediaType }), filename);
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
