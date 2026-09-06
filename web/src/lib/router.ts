import { readable } from "svelte/store";

/** Current pathname as a store. Updates on back/forward and on `navigate()`. */
export const path = readable(window.location.pathname, (set) => {
  const update = () => set(window.location.pathname);
  window.addEventListener("popstate", update);
  return () => window.removeEventListener("popstate", update);
});

export function navigate(to: string): void {
  if (to === window.location.pathname) return;
  window.history.pushState({}, "", to);
  window.dispatchEvent(new PopStateEvent("popstate"));
}

/** Pull a game code out of a `/r/<CODE>` deep link, else "". */
export function codeFromPath(p: string): string {
  const m = p.match(/^\/r\/([A-Za-z0-9]+)\/?$/);
  return m ? m[1].toUpperCase() : "";
}
