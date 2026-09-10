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
export type LibrarySong = {
  slug: string;
  name: string;
  durationMs: number;
  lineCount: number;
};

/** Create a one-device (pass-the-phone) game. Returns its code. */
export async function createSolo(): Promise<{ code: string }> {
  return post("/api/solo", undefined);
}

/** Enabled reference songs a host / solo player can pick instead of recording. */
export async function listSongs(): Promise<LibrarySong[]> {
  const res = await fetch("/api/songs");
  if (!res.ok) throw new Error(`request failed (${res.status})`);
  return res.json();
}

/** URL that streams a library song's clip, for previewing before picking it. */
export function songAudioUrl(
  slug: string,
  kind: "forward" | "reversed" = "forward"
): string {
  return `/api/songs/${encodeURIComponent(slug)}/audio/${kind}`;
}

/** Use a library song as the game's original (server copies its clips in and
 * moves the game to REVERSED_PLAYBACK). `playerId` required in multi-device. */
export async function pickOriginalFromLibrary(
  code: string,
  slug: string,
  playerId = ""
): Promise<OriginalResult> {
  const form = new FormData();
  form.append("slug", slug);
  form.append("playerId", playerId);
  return post(`/api/games/${code}/original/library`, form);
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
