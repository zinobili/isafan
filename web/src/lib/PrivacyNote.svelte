<!-- One-liner shown before a player commits to a game, so the retention policy
     (see server/retention.py) is stated up front rather than buried. The window
     tracks ISAFAN_GAME_TTL via /api/config so the copy can't drift from the
     actual purge age. -->
<script lang="ts">
  import { publicConfig } from "./config";

  let hours = 24; // sensible default until /api/config resolves
  publicConfig().then((c) => (hours = c.retentionHours));
</script>

<p class="privacy">
  {#if hours > 0}
    🔒 Recordings are kept up to {hours}&nbsp;{hours === 1 ? "hour" : "hours"} for
    a safety check, then deleted automatically.
  {:else}
    🔒 Recordings are stored on the host device until it clears them.
  {/if}
</p>

<style>
  .privacy {
    font-size: 0.8rem;
    line-height: 1.45;
    color: var(--muted);
  }
</style>
