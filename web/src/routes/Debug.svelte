<script lang="ts">
  import { onMount } from "svelte";
  import { connect, sendEcho, echoLog, connState } from "../lib/socket";
  import { navigate } from "../lib/router";

  let text = "hello";
  onMount(connect);

  function ping() {
    sendEcho({ msg: text, at: Date.now() });
  }
</script>

<div class="screen">
  <h1>WebSocket check</h1>
  <p>Sends an <span class="mono">echo</span> frame; the server echoes it back.</p>

  <div class="panel">
    <label>
      Payload text
      <input bind:value={text} />
    </label>
    <button on:click={ping}>Send echo</button>
    <div class="status">connection: {$connState}</div>
  </div>

  <div class="panel">
    <h2>Replies</h2>
    <div class="list">
      {#each $echoLog as line}
        <div class="list-item mono">{line}</div>
      {:else}
        <p>No replies yet.</p>
      {/each}
    </div>
  </div>

  <button class="secondary" on:click={() => navigate("/")}>Back</button>
</div>
