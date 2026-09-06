<script lang="ts">
  import { path } from "./lib/router";
  import Join from "./routes/Join.svelte";
  import Host from "./routes/Host.svelte";
  import Solo from "./routes/Solo.svelte";
  import Debug from "./routes/Debug.svelte";
  import NotFound from "./routes/NotFound.svelte";

  $: p = $path;
</script>

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
