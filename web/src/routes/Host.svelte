<script lang="ts">
  import { onMount } from "svelte";
  import QRCode from "qrcode";
  import {
    connect,
    createGame,
    leaveGame,
    startSongRecording,
    resetRound,
    startAudienceRecording,
    startReveal,
    nextRound,
    setRevealOriginal,
    game,
    me,
    lastError,
    connState,
    resyncNonce,
  } from "../lib/socket";
  import { navigate } from "../lib/router";
  import { publicConfig } from "../lib/config";
  import { uploadOriginal, pickOriginalFromLibrary } from "../lib/api";
  import type { Recording } from "../lib/audio";
  import Lobby from "../lib/Lobby.svelte";
  import PlayClip from "../lib/PlayClip.svelte";
  import RecordControl from "../lib/RecordControl.svelte";
  import SongPicker from "../lib/SongPicker.svelte";
  import RevealPanel from "../lib/RevealPanel.svelte";

  let name = "Host";
  let qr = "";
  let candidates: string[] = [location.origin];
  let chosen = location.origin;
  const secure = window.isSecureContext === true;

  // HOST_RECORDING upload state
  let busy = false;
  let err = "";

  // Clear transient upload state after a silent reconnect resync.
  let seenNonce = 0;
  $: if ($resyncNonce !== seenNonce) {
    seenNonce = $resyncNonce;
    busy = false;
    err = "";
  }

  onMount(async () => {
    connect();
    const cfg = await publicConfig();
    candidates = cfg.candidates;
    chosen = cfg.base;
  });

  const pretty = (u: string) => u.replace(/^https?:\/\//, "");

  $: joinUrl = $game ? `${chosen}/r/${$game.code}` : "";
  $: if (joinUrl) {
    QRCode.toDataURL(joinUrl, { margin: 1, width: 400 })
      .then((d: string) => (qr = d))
      .catch(() => (qr = ""));
  }

  async function onSongTake(e: CustomEvent<{ recording: Recording }>) {
    if (!$game || !$me) return;
    busy = true;
    err = "";
    try {
      await uploadOriginal($game.code, $me.id, e.detail.recording);
      // server broadcasts phase REVERSED_PLAYBACK
    } catch (x) {
      err = x instanceof Error ? x.message : String(x);
    } finally {
      busy = false;
    }
  }

  async function onPickSong(e: CustomEvent<{ slug: string }>) {
    if (!$game || !$me) return;
    busy = true;
    err = "";
    try {
      await pickOriginalFromLibrary($game.code, e.detail.slug, $me.id);
      // server broadcasts phase REVERSED_PLAYBACK
    } catch (x) {
      err = x instanceof Error ? x.message : String(x);
    } finally {
      busy = false;
    }
  }

  // --- AUDIENCE_RECORDING: who still owes a take (everyone but the singer) ---
  $: audience = ($game?.players ?? []).filter((p) => p.id !== $game?.hostId);
  $: didSubmit = (pid: string) => ($game?.attempts ?? []).some((a) => a.by === pid);
  $: submittedCount = audience.filter((p) => didSubmit(p.id)).length;
  $: allIn = audience.length > 0 && submittedCount === audience.length;

  function reveal() {
    if (allIn || confirm("Reveal without everyone's take?")) startReveal();
  }
</script>

<div class="screen">
  {#if $game && $me}
    <div class="row">
      <h1>👥 Multiplayer</h1>
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
      {#if !secure}
        <p class="note">
          Plain HTTP — phones will record with their own voice recorder instead of
          in the page. For in-page recording without a tunnel, see the README (mkcert).
        </p>
      {/if}
    </div>

    <Lobby />

    {#if $game.phase === "LOBBY"}
      <div class="panel">
        <h2>The song</h2>
        <p>One person sings a line or two. Everyone else will hear it backwards.</p>
        <button on:click={startSongRecording}>Record the song</button>
        <SongPicker {busy} on:pick={onPickSong} />
        {#if err}<span class="err">{err}</span>{/if}
      </div>
    {:else if $game.phase === "HOST_RECORDING"}
      <div class="panel">
        <h2>Record the song</h2>
        <p>Sing a line or two, listen back, then send it.</p>
        {#key $resyncNonce}
          <RecordControl {busy} useLabel="Use this take" on:done={onSongTake} />
        {/key}
        <SongPicker {busy} on:pick={onPickSong} />
        {#if err}<span class="err">{err}</span>{/if}
      </div>
    {:else if $game.phase === "REVERSED_PLAYBACK"}
      <div class="panel">
        <h2>Reversed clip is ready</h2>
        <p>Players can hear it on their phones. When everyone's had a listen:</p>
        {#if $game.original}
          <PlayClip url={$game.original.url} label="The reversed clip" />
        {/if}
        <label class="toggle">
          <input
            type="checkbox"
            checked={$game.revealOriginal}
            on:change={(e) => setRevealOriginal(e.currentTarget.checked)}
          />
          Let players also hear the original song (easier)
        </label>
        <button on:click={startAudienceRecording}>Start the round — everyone records</button>
        <div class="row">
          <button class="secondary" on:click={startSongRecording}>Re-record the song</button>
          <button class="secondary" on:click={resetRound}>Back to lobby</button>
        </div>
      </div>
    {:else if $game.phase === "AUDIENCE_RECORDING"}
      <div class="panel">
        <h2>Everyone's recording…</h2>
        {#if audience.length === 0}
          <p>No players have joined yet.</p>
          <button class="secondary" on:click={resetRound}>Back to lobby</button>
        {:else}
          <p>{submittedCount} of {audience.length} takes in.</p>
          <div class="list">
            {#each audience as p (p.id)}
              <div class="list-item">
                <span class="dot" class:off={!didSubmit(p.id)}></span>
                <span>{p.name}</span>
                <span class="spacer"></span>
                <span>{didSubmit(p.id) ? "✓ in" : "…"}</span>
              </div>
            {/each}
          </div>
          <button on:click={reveal}>
            {allIn ? "Reveal the takes" : `Reveal now (${submittedCount}/${audience.length})`}
          </button>
        {/if}
      </div>
    {:else if $game.phase === "REVEAL"}
      <div class="panel">
        <h2>The takes — forwards</h2>
        <RevealPanel
          attempts={$game.attempts}
          votes={$game.votes}
          originalForwardUrl={$game.original?.forwardUrl}
        />
        <div class="row">
          <button on:click={nextRound}>Next round</button>
          <button class="secondary" on:click={resetRound}>Back to lobby</button>
        </div>
      </div>
    {/if}
  {:else}
    <h1>👥 Multiplayer</h1>
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
  .note {
    font-size: 0.72rem;
    color: var(--warn);
    text-align: center;
  }
  .toggle {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 0.85rem;
    color: var(--muted);
  }
  .toggle input {
    width: auto;
  }
</style>
