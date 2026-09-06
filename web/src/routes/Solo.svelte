<script lang="ts">
  import { navigate } from "../lib/router";
  import { createSolo, uploadOriginal, uploadAttempt } from "../lib/api";
  import RecordControl from "../lib/RecordControl.svelte";
  import PlayClip from "../lib/PlayClip.svelte";
  import type { Recording } from "../lib/audio";

  type Step = "intro" | "original" | "listen" | "attempts" | "reveal";
  let step: Step = "intro";

  let names: string[] = ["", ""];
  let code = "";
  let originalUrl = "";
  let attempts: { name: string; url: string }[] = [];
  let idx = 0;
  let votes: number[] = [];
  let busy = false;
  let err = "";

  $: clean = names.map((n) => n.trim()).filter(Boolean);
  $: canStart = clean.length >= 2;
  $: current = clean[idx] ?? "";

  function addName() {
    names = [...names, ""];
  }
  function removeName(i: number) {
    names = names.filter((_, j) => j !== i);
  }

  function start() {
    if (!canStart) return;
    names = clean;
    step = "original";
  }

  async function onOriginal(e: CustomEvent<{ recording: Recording }>) {
    busy = true;
    err = "";
    try {
      code = (await createSolo()).code;
      originalUrl = (await uploadOriginal(code, "", e.detail.recording)).url;
      step = "listen";
    } catch (x) {
      err = x instanceof Error ? x.message : String(x);
    } finally {
      busy = false;
    }
  }

  async function onAttempt(e: CustomEvent<{ recording: Recording }>) {
    busy = true;
    err = "";
    try {
      const r = await uploadAttempt(code, current, e.detail.recording);
      attempts = [...attempts, { name: current, url: r.url }];
      idx += 1;
      if (idx >= names.length) {
        votes = attempts.map(() => 0);
        step = "reveal";
      }
    } catch (x) {
      err = x instanceof Error ? x.message : String(x);
    } finally {
      busy = false;
    }
  }

  function vote(i: number) {
    votes[i] += 1;
    votes = votes;
  }

  $: topVotes = Math.max(0, ...votes);
  $: leaders = attempts.filter((_, i) => topVotes > 0 && votes[i] === topVotes);

  function playAgain() {
    code = "";
    originalUrl = "";
    attempts = [];
    idx = 0;
    votes = [];
    err = "";
    step = "original";
  }
  function newGame() {
    names = ["", ""];
    playAgain();
    step = "intro";
  }
</script>

<div class="screen">
  <div class="row">
    <h1>📱 One device</h1>
    <span class="spacer"></span>
    <button class="secondary" on:click={() => navigate("/")}>Exit</button>
  </div>

  {#if step === "intro"}
    <p>Pass this phone around. One person sings, everyone else mimics the reversed clip.</p>
    <div class="panel">
      <h2>Who's playing?</h2>
      <div class="list">
        {#each names as _, i}
          <div class="row">
            <input bind:value={names[i]} maxlength="24" placeholder={`Player ${i + 1}`} />
            {#if names.length > 2}
              <button class="secondary" on:click={() => removeName(i)}>✕</button>
            {/if}
          </div>
        {/each}
      </div>
      <button class="secondary" on:click={addName}>+ Add player</button>
      <button on:click={start} disabled={!canStart}>Start</button>
    </div>
  {:else if step === "original"}
    <div class="panel">
      <h2>Record the song</h2>
      <p>Sing a line or two. Everyone else will hear it backwards.</p>
      <RecordControl {busy} useLabel="Reverse it" on:done={onOriginal} />
      {#if err}<span class="err">{err}</span>{/if}
    </div>
  {:else if step === "listen"}
    <div class="panel">
      <h2>Here it is — backwards</h2>
      <p>Play it for everyone a few times.</p>
      <PlayClip url={originalUrl} label="The reversed clip" />
      <button on:click={() => (step = "attempts")}>Everyone's ready — start the round</button>
    </div>
  {:else if step === "attempts"}
    <div class="panel">
      <h2>{current}'s turn</h2>
      <p>Player {idx + 1} of {names.length}. Hear it again, then sing it back.</p>
      <PlayClip url={originalUrl} label="The reversed clip" />
      {#key idx}
        <RecordControl {busy} useLabel="Keep this take" on:done={onAttempt} />
      {/key}
      {#if err}<span class="err">{err}</span>{/if}
    </div>
  {:else if step === "reveal"}
    <div class="panel">
      <h2>Now — forwards</h2>
      <p>Each take, reversed back. Closest to the original wins.</p>
      <div class="list">
        {#each attempts as a, i}
          <div class="take">
            <div class="row">
              <strong>{a.name}</strong>
              <span class="spacer"></span>
              <button class="secondary" on:click={() => vote(i)}>
                Vote{votes[i] ? ` · ${votes[i]}` : ""}
              </button>
            </div>
            <PlayClip url={a.url} />
          </div>
        {/each}
      </div>
      <PlayClip url={originalUrl} label="The original" />
      {#if leaders.length}
        <p><strong>{leaders.map((l) => l.name).join(", ")}</strong> {leaders.length > 1 ? "tie" : "wins"}!</p>
      {/if}
    </div>
    <div class="row">
      <button on:click={playAgain}>Play again (same players)</button>
      <button class="secondary" on:click={newGame}>New game</button>
    </div>
  {/if}

  {#if code}<div class="status">game {code}</div>{/if}
</div>

<style>
  .take {
    background: var(--bg);
    border-radius: 10px;
    padding: 10px 12px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }
</style>
