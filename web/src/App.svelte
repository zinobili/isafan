<script lang="ts">
  import { path } from "./lib/router";
  import Join from "./routes/Join.svelte";
  import Host from "./routes/Host.svelte";
  import Solo from "./routes/Solo.svelte";
  import Debug from "./routes/Debug.svelte";
  import NotFound from "./routes/NotFound.svelte";

  $: p = $path;
</script>

<div class="brand">Isafan</div>

{#if p === "/" || p.startsWith("/r/")}
  <Join />
{:else if p === "/host"}
  <Host />
{:else if p === "/solo"}
  <Solo />
{:else if p === "/debug"}
  <Debug />
{:else}
  <NotFound />
{/if}

<style>
  .brand {
    align-self: center;
    font-weight: 800;
    font-size: clamp(1.9rem, 8vw, 2.6rem);
    letter-spacing: 0.28em;
    padding-left: 0.28em; /* balance the trailing letter-spacing */
    text-transform: uppercase;
    color: var(--accent);
    margin: 4px 0 18px;
  }
</style>
