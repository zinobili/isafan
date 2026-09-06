<script lang="ts">
  export let url: string;
  export let label = "";
</script>

<div class="clip">
  {#if label}<span class="clip-label">{label}</span>{/if}
  <audio controls preload="metadata" src={url}></audio>
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
</style>
