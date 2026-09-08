/** Best-effort screen Wake Lock: keep a phone's screen on while a round is
 *  recording so it doesn't sleep mid-take. A silent no-op where the API is
 *  missing (older Safari), the context is insecure, or the request is denied.
 *  The OS drops the lock whenever the tab is hidden, so we re-acquire it on
 *  the next `visibilitychange` back to visible. */

let sentinel: WakeLockSentinel | null = null;
let wanted = false;

async function acquire(): Promise<void> {
  if (!wanted || sentinel || !("wakeLock" in navigator)) return;
  try {
    sentinel = await navigator.wakeLock.request("screen");
    sentinel.addEventListener("release", () => {
      sentinel = null;
    });
  } catch {
    sentinel = null; // denied, or not allowed in this state — nothing to do
  }
}

/** Start holding the screen awake. Idempotent. */
export function keepAwake(): void {
  wanted = true;
  void acquire();
}

/** Release the lock. Idempotent; safe to call when nothing is held. */
export function releaseWake(): void {
  wanted = false;
  const held = sentinel;
  sentinel = null;
  void held?.release().catch(() => {});
}

if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (wanted && document.visibilityState === "visible") void acquire();
  });
}
