import { writable } from "svelte/store";

export type PlayerView = {
  id: string;
  name: string;
  isHost: boolean;
  connected: boolean;
};

export type GameView = {
  code: string;
  mode: "multi" | "solo";
  phase: string;
  hostId: string | null;
  roundNo: number;
  createdAt: number;
  players: PlayerView[];
};

export type ConnState = "idle" | "connecting" | "open" | "closed";

export const connState = writable<ConnState>("idle");
export const game = writable<GameView | null>(null);
export const me = writable<{ id: string; code: string } | null>(null);
export const lastError = writable<string | null>(null);
/** Rolling log of echo replies — used by the /debug screen. */
export const echoLog = writable<string[]>([]);

const LS_KEY = "isafan.session";

let ws: WebSocket | null = null;
let outbox: unknown[] = [];
let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
let keepAlive: ReturnType<typeof setInterval> | null = null;
let backoff = 500;
let closedByUs = false;
let session: { code: string; playerId: string } | null = loadSession();

function loadSession(): { code: string; playerId: string } | null {
  try {
    const raw = localStorage.getItem(LS_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function saveSession(s: { code: string; playerId: string } | null): void {
  session = s;
  try {
    if (s) localStorage.setItem(LS_KEY, JSON.stringify(s));
    else localStorage.removeItem(LS_KEY);
  } catch {
    /* private mode / storage disabled — in-memory session still works */
  }
}

function wsUrl(): string {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  return `${proto}://${location.host}/ws`;
}

function send(obj: unknown): void {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(obj));
  else outbox.push(obj);
}

function scheduleReconnect(): void {
  if (reconnectTimer || closedByUs) return;
  reconnectTimer = setTimeout(() => {
    reconnectTimer = null;
    connect();
  }, backoff);
  backoff = Math.min(backoff * 2, 10_000);
}

export function connect(): void {
  if (
    ws &&
    (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }
  closedByUs = false;
  connState.set("connecting");
  ws = new WebSocket(wsUrl());

  ws.onopen = () => {
    backoff = 500;
    connState.set("open");
    if (session) {
      send({ type: "rejoin", code: session.code, playerId: session.playerId });
    }
    for (const m of outbox.splice(0)) send(m);
    keepAlive ??= setInterval(() => send({ type: "ping" }), 20_000);
  };

  ws.onmessage = (ev) => {
    let msg: any;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    handle(msg);
  };

  ws.onclose = () => {
    ws = null;
    if (keepAlive) {
      clearInterval(keepAlive);
      keepAlive = null;
    }
    connState.set("closed");
    if (!closedByUs) scheduleReconnect();
  };

  ws.onerror = () => {
    /* onclose fires next and handles reconnect */
  };
}

function handle(msg: any): void {
  switch (msg?.type) {
    case "joined":
      me.set({ id: msg.playerId, code: msg.code });
      game.set(msg.game);
      lastError.set(null);
      saveSession({ code: msg.code, playerId: msg.playerId });
      break;
    case "game":
      game.set(msg.game);
      break;
    case "echo":
      echoLog.update((l) => [
        `${new Date().toLocaleTimeString()}  ${JSON.stringify(msg.payload)}`,
        ...l,
      ].slice(0, 20));
      break;
    case "error":
      lastError.set(msg.message ?? msg.code ?? "unknown error");
      if (msg.code === "game_not_found") {
        saveSession(null);
        game.set(null);
        me.set(null);
      }
      break;
    case "pong":
      break;
  }
}

// --- public actions --------------------------------------------------------

export function createGame(name: string, mode: "multi" | "solo" = "multi"): void {
  connect();
  lastError.set(null);
  send({ type: "create", name, mode });
}

export function joinGame(code: string, name: string): void {
  connect();
  lastError.set(null);
  send({ type: "join", code: code.trim().toUpperCase(), name });
}

export function leaveGame(): void {
  send({ type: "leave" });
  saveSession(null);
  game.set(null);
  me.set(null);
}

export function sendEcho(payload: unknown): void {
  connect();
  send({ type: "echo", payload });
}

export function hasSession(): boolean {
  return session !== null;
}
