<script lang="ts">
  import { game, me } from "./socket";

  $: g = $game;
  $: myId = $me?.id ?? null;
</script>

{#if g}
  <div class="panel">
    <div class="row">
      <h2>Players</h2>
      <span class="spacer"></span>
      <span class="pill">{g.players.length} in room</span>
    </div>

    <div class="list">
      {#each g.players as p (p.id)}
        <div class="list-item">
          <span class="dot" class:off={!p.connected}></span>
          <span>{p.name}{p.id === myId ? " (you)" : ""}</span>
          <span class="spacer"></span>
          {#if p.isHost}<span class="pill host">host</span>{/if}
        </div>
      {/each}
    </div>

    <p>Phase: <strong>{g.phase}</strong> · round {g.roundNo}</p>
  </div>
{/if}
