<script lang="ts">
  import { createEventDispatcher } from "svelte";
  import PlayClip from "./PlayClip.svelte";
  import type { AttemptView } from "./socket";

  export let attempts: AttemptView[] = [];
  export let votes: Record<string, string> = {};
  export let originalForwardUrl: string | undefined = undefined;
  /** set on player screens: shows vote buttons (own take disabled, my vote starred).
   *  leave unset on the host screen: shows vote counts only. */
  export let meId: string | undefined = undefined;

  const dispatch = createEventDispatcher<{ vote: string }>();

  function countVotes(atts: AttemptView[], v: Record<string, string>): Record<string, number> {
    const t: Record<string, number> = {};
    for (const a of atts) t[a.id] = 0;
    for (const aid of Object.values(v)) if (aid in t) t[aid] += 1;
    return t;
  }

  $: tally = countVotes(attempts, votes);
  $: top = Math.max(0, ...Object.values(tally));
  $: leaders = top > 0 ? attempts.filter((a) => tally[a.id] === top) : [];
  $: myVote = meId ? votes[meId] : undefined;
</script>

{#if attempts.length === 0}
  <p>Nobody recorded a take.</p>
{:else}
  <div class="list">
    {#each attempts as a (a.id)}
      <div class="take">
        <div class="row">
          <strong>{a.name}</strong>
          <span class="spacer"></span>
          {#if meId}
            <button
              class:active={myVote === a.id}
              disabled={a.by === meId}
              on:click={() => dispatch("vote", a.id)}
            >
              {myVote === a.id ? "★ Voted" : a.by === meId ? "Your take" : "Vote"}
            </button>
          {:else}
            <span class="pill">{tally[a.id]} {tally[a.id] === 1 ? "vote" : "votes"}</span>
          {/if}
        </div>
        <PlayClip url={a.url} />
      </div>
    {/each}
  </div>
{/if}

{#if originalForwardUrl}
  <PlayClip url={originalForwardUrl} label="The original song — how it should sound" />
{/if}

{#if leaders.length}
  <p class="winner">
    <strong>{leaders.map((l) => l.name).join(", ")}</strong>
    {leaders.length > 1 ? "tie so far" : "in the lead"}
  </p>
{/if}

<style>
  .take {
    background: var(--bg);
    border-radius: 10px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
  button.active {
    background: var(--ok);
    color: #05261a;
  }
  .winner {
    color: var(--text);
  }
</style>
