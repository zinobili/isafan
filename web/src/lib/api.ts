import type { Recording } from "./audio";

async function post(url: string, body: FormData | undefined) {
  const res = await fetch(url, { method: "POST", body });
  if (!res.ok) {
    let detail = `request failed (${res.status})`;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* keep default */
    }
    throw new Error(detail);
  }
  return res.json();
}

export type OriginalResult = { durationMs: number; url: string; forwardUrl: string };
export type AttemptResult = { id: string; name: string; durationMs: number; url: string };

/** Create a one-device (pass-the-phone) game. Returns its code. */
export async function createSolo(): Promise<{ code: string }> {
  return post("/api/solo", undefined);
}

/** Upload the sung take. Server reverses + transcodes it and moves the game to
 * REVERSED_PLAYBACK. `playerId` is required in multi-device mode, ignored in solo. */
export async function uploadOriginal(
  code: string,
  playerId: string,
  take: Recording
): Promise<OriginalResult> {
  const form = new FormData();
  form.append("playerId", playerId);
  form.append("file", take.blob, `original.${take.ext}`);
  return post(`/api/games/${code}/original`, form);
}

/** Upload one player's mimic. Returns the stored attempt with its reversed URL. */
export async function uploadAttempt(
  code: string,
  name: string,
  take: Recording,
  playerId = ""
): Promise<AttemptResult> {
  const form = new FormData();
  form.append("name", name);
  form.append("playerId", playerId);
  form.append("file", take.blob, `attempt.${take.ext}`);
  return post(`/api/games/${code}/attempts`, form);
}
