<script lang="ts">
  import { onMount } from "svelte";
  import QRCode from "qrcode";
  import {
    connect,
    createGame,
    leaveGame,
    startRecording,
    resetRound,
    game,
    me,
    lastError,
    connState,
  } from "../lib/socket";
  import { navigate } from "../lib/router";
  import { publicConfig } from "../lib/config";
  import { startRecording as micStart, micSupported, type Recording } from "../lib/audio";
  import { uploadOriginal } from "../lib/api";
  import Lobby from "../lib/Lobby.svelte";
  import PlayClip from "../lib/PlayClip.svelte";

  let name = "Host";
  let qr = "";
  let candidates: string[] = [location.origin];
  let chosen = location.origin;

  // local state for the HOST_RECORDING phase
  type Ui = "idle" | "recording" | "preview" | "uploading";
  let ui: Ui = "idle";
  let handle: Awaited<ReturnType<typeof micStart>> | null = null;
  let take: Recording | null = null;
  let takeUrl = "";
  let elapsed = 0;
  let timer: ReturnType<typeof setInterval> | null = null;
  let err = "";

  onMount(async () => {
    connect();
    const cfg = await publicConfig();
    candidates = cfg.candidates;
    chosen = cfg.base;
  });

  $: joinUrl = $game ? `${chosen}/r/${$game.code}` : "";
  $: pretty = (u: string) => u.replace(/^https?:\/\//, "");
  $: if (joinUrl) {
    QRCode.toDataURL(joinUrl, { margin: 1, width: 400 })
      .then((d: string) => (qr = d))
      .catch(() => (qr = ""));
  }
  // reset local recorder state whenever we (re-)enter the recording phase
  $: if ($game?.phase === "HOST_RECORDING" && ui !== "recording" && ui !== "preview" && ui !== "uploading") {
    clearTake();
  }

  function clearTake() {
    if (takeUrl) URL.revokeObjectURL(takeUrl);
    take = null;
    takeUrl = "";
    elapsed = 0;
    err = "";
    ui = "idle";
  }

  async function beginRecording() {
    err = "";
    try {
      handle = await micStart();
      ui = "recording";
      elapsed = 0;
      timer = setInterval(() => (elapsed += 1), 1000);
    } catch (e) {
      err = e instanceof Error ? e.message : String(e);
    }
  }

  async function stopRecording() {
    if (timer) clearInterval(timer);
    timer = null;
    if (!handle) return;
    take = await handle.stop();
    handle = null;
    takeUrl = URL.createObjectURL(take.blob);
    ui = "preview";
  }

  async function submit() {
    if (!take || !$game || !$me) return;
    ui = "uploading";
    err = "";
    try {
      await uploadOriginal($game.code, $me.id, take);
      // server broadcasts phase REVERSED_PLAYBACK; local state resets on next enter
      clearTake();
    } catch (e) {
      err = e instanceof Error ? e.message : String(e);
      ui = "preview";
    }
  }

  function fmt(s: number) {
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }
</script>

<div class="screen">
  {#if $game && $me}
    <div class="row">
      <h1>Host screen</h1>
      <span class="spacer"></span>
      <button class="secondary" on:click={leaveGame}>End</button>
    </div>

    <div class="panel">
      <h2>Join code</h2>
      <div class="code">{$game.code}</div>
      {#if qr}<div class="qr"><img src={qr} alt="QR code to join" /></div>{/if}
      <p style="text-align:center">
        Open <span class="mono">{joinUrl}</span> on your phone, or scan the code.
      </p>
      {#if candidates.length > 1}
        <div class="alts">
          <span>Phone can't reach it? Try:</span>
          {#each candidates as c}
            <button class:active={c === chosen} on:click={() => (chosen = c)}>
              {pretty(c)}
            </button>
          {/each}
        </div>
      {/if}
    </div>

    <Lobby />

    {#if $game.phase === "LOBBY"}
      <div class="panel">
        <h2>The song</h2>
        <p>One person sings a line or two. Everyone else will hear it backwards.</p>
        <button on:click={startRecording}>Record the song</button>
      </div>
    {:else if $game.phase === "HOST_RECORDING"}
      <div class="panel">
        <h2>Record the song</h2>
        {#if !micSupported()}
          <span class="err">
            This browser can't record audio. Use Chrome/Safari on an HTTPS page.
          </span>
        {/if}

        {#if ui === "idle"}
          <p>Tap to start, sing, then tap stop.</p>
          <button on:click={beginRecording} disabled={!micSupported()}>Start recording</button>
        {:else if ui === "recording"}
          <p>Recording… <strong>{fmt(elapsed)}</strong></p>
          <button on:click={stopRecording}>Stop</button>
        {:else if ui === "preview"}
          <p>Listen back, then send it — or record again.</p>
          <audio controls src={takeUrl}></audio>
          <div class="row">
            <button on:click={submit}>Use this take</button>
            <button class="secondary" on:click={beginRecording}>Redo</button>
          </div>
        {:else if ui === "uploading"}
          <p>Reversing…</p>
        {/if}

        {#if err}<span class="err">{err}</span>{/if}
      </div>
    {:else if $game.phase === "REVERSED_PLAYBACK"}
      <div class="panel">
        <h2>Reversed clip is ready</h2>
        <p>Players can now hear it on their phones. Play it here too:</p>
        {#if $game.original}
          <PlayClip url={$game.original.url} label="▶ Play reversed clip" />
        {/if}
        <div class="row">
          <button class="secondary" on:click={startRecording}>Re-record the song</button>
          <button class="secondary" on:click={resetRound}>Back to lobby</button>
        </div>
      </div>
    {/if}
  {:else}
    <h1>Host a game</h1>
    <p>Create a room, then share the code with the players on their phones.</p>
    <div class="panel">
      <label>
        Host name
        <input bind:value={name} maxlength="24" autocomplete="off" />
      </label>
      {#if $lastError}<span class="err">{$lastError}</span>{/if}
      <button on:click={() => createGame(name)} disabled={!name.trim()}>Create game</button>
    </div>
    <button class="secondary" on:click={() => navigate("/")}>Back to join</button>
  {/if}

  <div class="status">connection: {$connState}</div>
</div>

<style>
  .alts {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    justify-content: center;
    align-items: center;
    font-size: 0.72rem;
    color: var(--muted);
  }
  .alts button {
    background: var(--panel-2);
    color: var(--muted);
    border: 0;
    padding: 4px 8px;
    border-radius: 8px;
    font-size: 0.72rem;
    min-height: 0;
    cursor: pointer;
  }
  .alts button.active {
    background: var(--accent);
    color: #fff;
  }
</style>
