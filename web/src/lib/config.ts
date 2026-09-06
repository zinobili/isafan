/**
 * Base URL for links shown to players (the join link and its QR code).
 *
 * Defaults to the origin the page was opened with. If the server has
 * `ISAFAN_PUBLIC_URL` set, that wins — so you can keep the host screen on
 * `localhost` while the QR points at a LAN IP or tunnel URL. Fetched once.
 */
let cached: Promise<string> | null = null;

export function publicBase(): Promise<string> {
  cached ??= fetch("/api/config")
    .then((r) => (r.ok ? r.json() : { publicUrl: "" }))
    .then((c) => String(c.publicUrl || location.origin).replace(/\/+$/, ""))
    .catch(() => location.origin);
  return cached;
}
