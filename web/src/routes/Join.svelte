<script lang="ts">
  import { onMount } from "svelte";
  import {
    connect,
    joinGame,
    leaveGame,
    castVote,
    game,
    me,
    lastError,
    connState,
    resyncNonce,
  } from "../lib/socket";
  import { navigate, path, codeFromPath } from "../lib/router";
  import { uploadAttempt } from "../lib/api";
  import type { Recording } from "../lib/audio";
  import HowToPlay from "../lib/HowToPlay.svelte";
  import Lobby from "../lib/Lobby.svelte";
  import PlayClip from "../lib/PlayClip.svelte";
  import PrivacyNote from "../lib/PrivacyNote.svelte";
  import RecordControl from "../lib/RecordControl.svelte";
  import RevealPanel from "../lib/RevealPanel.svelte";

  let name = "";
  let code = codeFromPath($path);

  // Keep the field in sync if the user lands on /r/<CODE>.
  $: code = code || codeFromPath($path);

  onMount(() => {
    connect(); // resumes an existing session via rejoin, if any
  });

  function submit() {
    if (!name.trim() || code.trim().length < 3) return;
    joinGame(code, name);
  }

  // --- AUDIENCE_RECORDING: record + submit my mimic ---
  let busy = false;
  let recErr = "";
  let redoing = false;

  $: myName = $game?.players.find((p) => p.id === $me?.id)?.name ?? "";
  $: iSubmitted = !!($game && $me && $game.attempts.some((a) => a.by === $me.id));
  $: if ($game && $game.phase !== "AUDIENCE_RECORDING") redoing = false;

  // After a silent reconnect, drop any half-finished local recording state and
  // let the screen re-derive from the fresh game snapshot.
  let seenNonce = 0;
  $: if ($resyncNonce !== seenNonce) {
    seenNonce = $resyncNonce;
    busy = false;
    recErr = "";
    redoing = false;
  }

  async function onSubmit(e: CustomEvent<{ recording: Recording }>) {
    if (!$game || !$me) return;
    busy = true;
    recErr = "";
    try {
      await uploadAttempt($game.code, myName, e.detail.recording, $me.id);
      redoing = false;
    } catch (x) {
      recErr = x instanceof Error ? x.message : String(x);
    } finally {
      busy = false;
    }
  }
</script>

{#if $game && $me}
  <div class="screen">
    <div class="row">
      <h1>Room {$game.code}</h1>
      <span class="spacer"></span>
      <button class="secondary" on:click={leaveGame}>Leave</button>
    </div>

    <HowToPlay />

    {#if $game.phase === "HOST_RECORDING"}
      <p>The host is recording the song…</p>
    {:else if $game.phase === "REVERSED_PLAYBACK" && $game.original}
      <div class="panel">
        <h2>Here it is — backwards</h2>
        <p>Listen as many times as you like. You'll sing it back next.</p>
        <PlayClip url={$game.original.url} label="The reversed clip" />
        {#if $game.revealOriginal}
          <PlayClip url={$game.original.forwardUrl} label="The original song (forwards)" />
        {/if}
      </div>
    {:else if $game.phase === "AUDIENCE_RECORDING"}
      {#if iSubmitted && !redoing}
        <div class="panel">
          <h2>You're in ✓</h2>
          <p>Waiting for the others to finish…</p>
          <button class="secondary" on:click={() => (redoing = true)}>Redo my take</button>
        </div>
      {:else}
        <div class="panel">
          <h2>Sing it back</h2>
          <p>Play the reversed clip, then record your version of it.</p>
          {#if $game.original}
            <PlayClip url={$game.original.url} label="The reversed clip" />
          {/if}
          {#key `${redoing}:${$resyncNonce}`}
            <RecordControl {busy} useLabel="Submit my take" on:done={onSubmit} />
          {/key}
          {#if recErr}<span class="err">{recErr}</span>{/if}
        </div>
      {/if}
    {:else if $game.phase === "REVEAL"}
      <div class="panel">
        <h2>Vote for the closest</h2>
        <RevealPanel
          attempts={$game.attempts}
          votes={$game.votes}
          originalForwardUrl={$game.original?.forwardUrl}
          meId={$me.id}
          on:vote={(e) => castVote(e.detail)}
        />
      </div>
    {:else}
      <p>Waiting for the host to start the game.</p>
    {/if}

    <Lobby />
  </div>
{:else}
  <div class="screen">
    <h1>Join a game</h1>
    <p>Enter the room code shown on the host screen.</p>

    <div class="panel">
      <label>
        Your name
        <input
          bind:value={name}
          maxlength="24"
          autocomplete="off"
          placeholder="e.g. Sam"
        />
      </label>
      <label>
        Room code
        <input
          bind:value={code}
          maxlength="8"
          autocapitalize="characters"
          autocomplete="off"
          spellcheck="false"
          placeholder="ABCD"
          on:input={(e) => (code = e.currentTarget.value.toUpperCase())}
        />
      </label>

      {#if $lastError}<span class="err">{$lastError}</span>{/if}

      <button on:click={submit} disabled={!name.trim() || code.trim().length < 3}>
        Join
      </button>

      <PrivacyNote />
    </div>

    <div class="row">
      <button class="secondary" on:click={() => navigate("/host")}>Host a game</button>
      <button class="secondary" on:click={() => navigate("/solo")}>One device</button>
    </div>
    <div class="status">connection: {$connState}</div>
  </div>
{/if}
