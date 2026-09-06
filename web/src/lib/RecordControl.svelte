<script lang="ts">
  import { createEventDispatcher, onDestroy } from "svelte";
  import {
    startRecording,
    canRecordInline,
    recordingFromFile,
    type Recording,
  } from "./audio";

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
    try {
      handle = await startRecording({ onActive });
      // safety net if a browser never emits an early dataavailable
      setTimeout(() => ui === "warming" && onActive(), 1200);
    } catch (e) {
      err = e instanceof Error ? e.message : String(e);
      ui = "idle";
    }
  }

  async function stop() {
    stopTimer();
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
    handle?.cancel();
    if (takeUrl) URL.revokeObjectURL(takeUrl);
  });
</script>

{#if ui === "idle"}
  {#if inline}
    <p>{hint}</p>
    <button on:click={begin} disabled={busy}>Start recording</button>
  {:else}
    <p>In-page recording needs HTTPS. Tap below to record with your phone.</p>
    <label class="filepick" class:disabled={busy}>
      <input
        type="file"
        accept="audio/*"
        capture="user"
        on:change={onFile}
        disabled={busy}
      />
      🎤 Record audio
    </label>
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
    .rec-dot {
      animation: none;
    }
  }
</style>
