/**
 * Base URL(s) for links shown to players (the join link and its QR code).
 *
 * `base` is the server's best guess: an explicit `ISAFAN_PUBLIC_URL`, else an
 * auto-detected LAN address, else the origin this page was opened with.
 * `candidates` holds every address the server thinks might work, so the host
 * screen can offer alternates when a phone can't reach the first one. Fetched
 * once and cached.
 */
export type PublicConfig = { base: string; candidates: string[] };

const strip = (u: string) => String(u).replace(/\/+$/, "");

let cached: Promise<PublicConfig> | null = null;

export function publicConfig(): Promise<PublicConfig> {
  cached ??= fetch("/api/config")
    .then((r) => (r.ok ? r.json() : {}))
    .then((c: { publicUrl?: string; publicUrlCandidates?: string[] }) => {
      const base = strip(c.publicUrl || location.origin);
      const list = Array.isArray(c.publicUrlCandidates) ? c.publicUrlCandidates : [];
      const candidates = list.length ? list.map(strip) : [base];
      return { base, candidates };
    })
    .catch(() => ({ base: location.origin, candidates: [location.origin] }));
  return cached;
}

export function publicBase(): Promise<string> {
  return publicConfig().then((c) => c.base);
}
