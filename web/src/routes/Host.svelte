<script lang="ts">
  import { onMount } from "svelte";
  import QRCode from "qrcode";
  import { connect, createGame, leaveGame, game, me, lastError, connState } from "../lib/socket";
  import { navigate } from "../lib/router";
  import { publicBase } from "../lib/config";
  import Lobby from "../lib/Lobby.svelte";

  let name = "Host";
  let qr = "";
  let base = location.origin;

  onMount(async () => {
    connect();
    base = await publicBase();
  });

  $: joinUrl = $game ? `${base}/r/${$game.code}` : "";
  $: if (joinUrl) {
    QRCode.toDataURL(joinUrl, { margin: 1, width: 400 })
      .then((d: string) => (qr = d))
      .catch(() => (qr = ""));
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
      {#if qr}
        <div class="qr"><img src={qr} alt="QR code to join" /></div>
      {/if}
      <p style="text-align:center">
        Open <span class="mono">{joinUrl}</span> on your phone, or scan the code.
      </p>
    </div>

    <Lobby />

    <button disabled title="Recording comes in a later phase">
      Start round (not built yet)
    </button>
  {:else}
    <h1>Host a game</h1>
    <p>Create a room, then share the code with the players on their phones.</p>
    <div class="panel">
      <label>
        Host name
        <input bind:value={name} maxlength="24" autocomplete="off" />
      </label>
      {#if $lastError}<span class="err">{$lastError}</span>{/if}
      <button on:click={() => createGame(name)} disabled={!name.trim()}>
        Create game
      </button>
    </div>
    <button class="secondary" on:click={() => navigate("/")}>Back to join</button>
  {/if}

  <div class="status">connection: {$connState}</div>
</div>
