<script lang="ts">
  import { playUrl } from "./audio";

  export let url: string;
  export let label = "Play";

  let playing = false;
  let error = "";

  async function play() {
    error = "";
    playing = true;
    try {
      await playUrl(url);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
    } finally {
      playing = false;
    }
  }
</script>

<button on:click={play} disabled={playing}>
  {playing ? "Playing…" : label}
</button>
{#if error}<span class="err">{error}</span>{/if}
