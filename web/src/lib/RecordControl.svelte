<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import {
    startRecording,
    canRecordInline,
    recordingFromFile,
    type Recording,
  } from "./audio";
  import { keepAwake, releaseWake } from "./wakelock";

  export let hint = "Tap start, sing, then tap stop.";
  export let useLabel = "Use this take";
  /** parent sets this true while it uploads; we lock the buttons + show a spinner */
  export let busy = false;

  const dispatch = createEventDispatcher<{ done: { recording: Recording } }>();

  // false on a plain-http LAN page: fall back to the phone's own recorder
  const inline = canRecordInline();

  type Ui = "idle" | "warming" | "recording" | "preview";
  let ui: Ui = "idle";
  let handle: Awaited<ReturnType<typeof startRecording>> | null = null;
  let take: Recording | null = null;
  let takeUrl = "";
  let elapsed = 0;
  let startedAt = 0;
  let timer: ReturnType<typeof setInterval> | null = null;
  let err = "";

  function stopTimer() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  /** back to the start — requires an explicit tap to record again */
  function toIdle() {
    stopTimer();
    releaseWake();
    if (takeUrl) URL.revokeObjectURL(takeUrl);
    take = null;
    takeUrl = "";
    elapsed = 0;
    err = "";
    ui = "idle";
  }

  function onActive() {
    if (timer) return; // guard: fires once, plus a fallback timeout
    startedAt = performance.now();
    elapsed = 0;
    ui = "recording";
    timer = setInterval(() => {
      elapsed = Math.floor((performance.now() - startedAt) / 1000);
    }, 250);
  }

  async function begin() {
    err = "";
    ui = "warming";
    keepAwake(); // hold the screen on for the take; released on stop / redo
    try {
      handle = await startRecording({ onActive });
      // safety net if a browser never emits an early dataavailable
      setTimeout(() => ui === "warming" && onActive(), 1200);
    } catch (e) {
      err = e instanceof Error ? e.message : String(e);
      releaseWake();
      ui = "idle";
    }
  }

  async function stop() {
    stopTimer();
    releaseWake();
    if (!handle) return;
    take = await handle.stop();
    handle = null;
    takeUrl = URL.createObjectURL(take.blob);
    ui = "preview";
  }

  function onFile(e: Event) {
    const input = e.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = ""; // allow re-picking the same file after a Redo
    if (!file) return;
    err = "";
    if (takeUrl) URL.revokeObjectURL(takeUrl);
    take = recordingFromFile(file);
    takeUrl = URL.createObjectURL(file);
    ui = "preview";
  }

  function use() {
    if (take) dispatch("done", { recording: take });
  }

  function fmt(s: number) {
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }

  onDestroy(() => {
    stopTimer();
    releaseWake();
    handle?.cancel();
    if (takeUrl) URL.revokeObjectURL(takeUrl);
  });
</script>

{#if ui === "warming" || ui === "recording"}
  <div class="rec-banner" role="status" aria-live="polite">
    <span class="rec-dot" aria-hidden="true"></span>
    <span>{ui === "warming" ? "Opening the mic…" : "Recording — your mic is live"}</span>
  </div>
{/if}

{#if ui === "idle"}
  {#if inline}
    <p>{hint}</p>
    <button on:click={begin} disabled={busy}>Start recording</button>
  {:else}
    <p>In-page recording needs HTTPS, so your phone's own recorder opens instead.</p>
    <label class="filepick" class:disabled={busy}>
      <input
        type="file"
        accept="audio/*"
        capture="environment"
        on:change={onFile}
        disabled={busy}
      />
      🎤 Record audio
    </label>
    <p class="fine">
      Your phone may open its <strong class="hl">video</strong> recorder — that's
      fine, record a few seconds.
      <strong class="safe">Only the audio is used; the video isn't stored, shown,
      or used for anything.</strong>
    </p>
  {/if}
{:else if ui === "warming"}
  <p>Opening the mic…</p>
  <button disabled>Starting…</button>
{:else if ui === "recording"}
  <div class="rec">
    <span class="rec-dot" aria-hidden="true"></span>
    <span class="rec-label">REC</span>
    <strong class="rec-time">{fmt(elapsed)}</strong>
  </div>
  <button on:click={stop}>Stop</button>
{:else if ui === "preview"}
  <p>Listen back, then keep it — or record again.</p>
  <audio controls src={takeUrl}></audio>
  <div class="row">
    <button on:click={use} disabled={busy}>{busy ? "Sending…" : useLabel}</button>
    <button class="secondary" on:click={toIdle} disabled={busy}>Redo</button>
  </div>
{/if}

{#if err}<span class="err">{err}</span>{/if}

<style>
  .filepick {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    font: inherit;
    font-weight: 600;
    padding: 13px 16px;
    border-radius: 11px;
    background: var(--accent);
    color: var(--accent-ink);
    cursor: pointer;
    min-height: 46px;
    text-align: center;
  }
  .filepick input {
    display: none;
  }
  .filepick.disabled {
    opacity: 0.5;
    pointer-events: none;
  }
  .fine {
    font-size: 0.9rem;
    line-height: 1.45;
    color: var(--muted);
  }
  .fine .hl {
    color: var(--warn);
  }
  .fine .safe {
    color: var(--ok);
  }

  .rec-banner {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    z-index: 100;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: calc(10px + env(safe-area-inset-top)) 14px 10px;
    background: var(--danger);
    color: #fff;
    font-weight: 700;
    font-size: 0.95rem;
    letter-spacing: 0.02em;
    box-shadow: 0 2px 14px rgb(0 0 0 / 0.35);
  }
  .rec-banner .rec-dot {
    background: #fff;
  }
  @keyframes rec-banner-pulse {
    0% {
      box-shadow: 0 0 0 0 rgb(255 255 255 / 0.6);
    }
    70% {
      box-shadow: 0 0 0 12px rgb(255 255 255 / 0);
    }
    100% {
      box-shadow: 0 0 0 0 rgb(255 255 255 / 0);
    }
  }
  .rec-banner .rec-dot {
    animation: rec-banner-pulse 1.1s ease-out infinite;
  }

  .rec {
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 1.05rem;
  }
  .rec-dot {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--danger);
    flex: none;
    animation: rec-pulse 1.1s ease-out infinite;
  }
  .rec-label {
    font-weight: 700;
    letter-spacing: 0.14em;
    color: var(--danger);
  }
  .rec-time {
    margin-left: auto;
    font-variant-numeric: tabular-nums;
  }
  @keyframes rec-pulse {
    0% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--danger) 65%, transparent);
      opacity: 1;
    }
    70% {
      box-shadow: 0 0 0 13px color-mix(in srgb, var(--danger) 0%, transparent);
      opacity: 0.7;
    }
    100% {
      box-shadow: 0 0 0 0 color-mix(in srgb, var(--danger) 0%, transparent);
      opacity: 1;
    }
  }
  @media (prefers-reduced-motion: reduce) {
    .rec-dot,
    .rec-banner .rec-dot {
      animation: none;
    }
  }
</style>
