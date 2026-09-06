<script lang="ts">
  export let url: string;
  export let label = "";

  let el: HTMLAudioElement;
  let failed = false;

  function retry() {
    failed = false;
    el?.load();
  }
</script>

<div class="clip">
  {#if label}<span class="clip-label">{label}</span>{/if}
  <!-- preload="none": on the reveal page several clips render at once; loading
       them all up front stampedes the server and iOS drops some. Load on tap. -->
  <audio
    bind:this={el}
    controls
    preload="none"
    src={url}
    on:error={() => (failed = true)}
    on:playing={() => (failed = false)}
  ></audio>
  {#if failed}
    <button class="secondary retry" on:click={retry}>Couldn't load — retry</button>
  {/if}
</div>

<style>
  .clip {
    display: flex;
    flex-direction: column;
    gap: 6px;
    width: 100%;
  }
  .clip-label {
    font-size: 0.8rem;
    color: var(--muted);
  }
  .retry {
    font-size: 0.8rem;
    padding: 6px 10px;
    min-height: 0;
    align-self: flex-start;
  }
</style>
