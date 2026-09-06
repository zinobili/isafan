<script lang="ts">
  import { onMount } from "svelte";
  import { connect, joinGame, leaveGame, game, me, lastError, connState } from "../lib/socket";
  import { navigate, path, codeFromPath } from "../lib/router";
  import Lobby from "../lib/Lobby.svelte";
  import PlayClip from "../lib/PlayClip.svelte";

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
</script>

{#if $game && $me}
  <div class="screen">
    <div class="row">
      <h1>Room {$game.code}</h1>
      <span class="spacer"></span>
      <button class="secondary" on:click={leaveGame}>Leave</button>
    </div>

    {#if $game.phase === "HOST_RECORDING"}
      <p>The host is recording the song…</p>
    {:else if $game.phase === "REVERSED_PLAYBACK" && $game.original}
      <div class="panel">
        <h2>Here it is — backwards</h2>
        <p>Listen as many times as you like. You'll sing it back next.</p>
        <PlayClip url={$game.original.url} label="▶ Play the reversed clip" />
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
    </div>

    <div class="row">
      <button class="secondary" on:click={() => navigate("/host")}>Host a game</button>
      <button class="secondary" on:click={() => navigate("/solo")}>One device</button>
    </div>
    <div class="status">connection: {$connState}</div>
  </div>
{/if}
