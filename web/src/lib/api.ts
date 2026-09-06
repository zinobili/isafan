import type { Recording } from "./audio";

export type OriginalResult = { durationMs: number; url: string };

/** Upload the host's sung take. The server reverses + transcodes it and moves
 * the game to REVERSED_PLAYBACK (delivered via the WebSocket `game` broadcast). */
export async function uploadOriginal(
  code: string,
  playerId: string,
  take: Recording
): Promise<OriginalResult> {
  const form = new FormData();
  form.append("playerId", playerId);
  form.append("file", take.blob, `original.${take.ext}`);

  const res = await fetch(`/api/games/${code}/original`, {
    method: "POST",
    body: form,
  });
  if (!res.ok) {
    let detail = `upload failed (${res.status})`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json();
}
