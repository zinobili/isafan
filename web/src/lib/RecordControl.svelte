<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import { startRecording, micSupported, type Recording } from "./audio";

  export let hint = "Tap start, sing, then tap stop.";
  export let useLabel = "Use this take";
  /** parent sets this true while it uploads; we show a spinner + lock buttons */
  export let busy = false;

  const dispatch = createEventDispatcher<{ done: { recording: Recording } }>();

  type Ui = "idle" | "recording" | "preview";
  let ui: Ui = "idle";
  let handle: Awaited<ReturnType<typeof startRecording>> | null = null;
  let take: Recording | null = null;
  let takeUrl = "";
  let elapsed = 0;
  let timer: ReturnType<typeof setInterval> | null = null;
  let err = "";

  function reset() {
    if (takeUrl) URL.revokeObjectURL(takeUrl);
    take = null;
    takeUrl = "";
    elapsed = 0;
    ui = "idle";
  }

  async function begin() {
    err = "";
    try {
      handle = await startRecording();
      ui = "recording";
      elapsed = 0;
      timer = setInterval(() => (elapsed += 1), 1000);
    } catch (e) {
      err = e instanceof Error ? e.message : String(e);
    }
  }

  async function stop() {
    if (timer) clearInterval(timer);
    timer = null;
    if (!handle) return;
    take = await handle.stop();
    handle = null;
    takeUrl = URL.createObjectURL(take.blob);
    ui = "preview";
  }

  function use() {
    if (take) dispatch("done", { recording: take });
  }

  function fmt(s: number) {
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }
</script>

{#if !micSupported()}
  <span class="err">This browser can't record audio. Use Chrome/Safari on an HTTPS page.</span>
{/if}

{#if ui === "idle"}
  <p>{hint}</p>
  <button on:click={begin} disabled={!micSupported() || busy}>Start recording</button>
{:else if ui === "recording"}
  <p>Recording… <strong>{fmt(elapsed)}</strong></p>
  <button on:click={stop}>Stop</button>
{:else if ui === "preview"}
  <p>Listen back, then keep it — or record again.</p>
  <audio controls src={takeUrl}></audio>
  <div class="row">
    <button on:click={use} disabled={busy}>{busy ? "Sending…" : useLabel}</button>
    <button class="secondary" on:click={begin} disabled={busy}>Redo</button>
  </div>
{/if}

{#if err}<span class="err">{err}</span>{/if}
