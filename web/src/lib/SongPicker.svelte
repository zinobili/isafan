<script lang="ts">
  import { onMount, createEventDispatcher } from "svelte";
  import { listSongs, type LibrarySong } from "./api";

  /** parent locks the buttons while it processes a pick */
  export let busy = false;
  /** heading shown above the list */
  export let label = "Or pick a ready-made song";

  const dispatch = createEventDispatcher<{ pick: { slug: string } }>();

  let songs: LibrarySong[] = [];
  let loaded = false;

  onMount(async () => {
    try {
      songs = await listSongs();
    } catch {
      songs = [];
    }
    loaded = true;
  });

  function fmt(ms: number) {
    const s = Math.round(ms / 1000);
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
  }
</script>

{#if loaded && songs.length}
  <div class="picker">
    <p class="pk-label">{label}</p>
    <div class="list">
      {#each songs as s (s.slug)}
        <button
          class="secondary song"
          disabled={busy}
          on:click={() => dispatch("pick", { slug: s.slug })}
        >
          <span class="name">{s.name}</span>
          <span class="meta">
            {fmt(s.durationMs)}{#if s.lineCount}
              · {s.lineCount} lines{/if}
          </span>
        </button>
      {/each}
    </div>
  </div>
{/if}

<style>
  .picker {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  .pk-label {
    font-size: 0.85rem;
    color: var(--muted);
  }
  .song {
    display: flex;
    align-items: baseline;
    gap: 10px;
    text-align: left;
    width: 100%;
  }
  .song .name {
    font-weight: 600;
  }
  .song .meta {
    margin-left: auto;
    font-size: 0.78rem;
    color: var(--muted);
  }
</style>
