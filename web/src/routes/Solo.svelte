<script lang="ts">
  import { navigate } from "../lib/router";
  import {
    createSolo,
    uploadOriginal,
    uploadAttempt,
    pickOriginalFromLibrary,
  } from "../lib/api";
  import RecordControl from "../lib/RecordControl.svelte";
  import SongPicker from "../lib/SongPicker.svelte";
  import PlayClip from "../lib/PlayClip.svelte";
  import PrivacyNote from "../lib/PrivacyNote.svelte";
  import type { Recording } from "../lib/audio";

  type Step = "intro" | "original" | "listen" | "attempts" | "reveal";
  let step: Step = "intro";

  let names: string[] = ["", ""];
  let code = "";
  let originalUrl = ""; // reversed — what players mimic
  let originalForwardUrl = ""; // the song as sung — for comparison at the reveal
  let attempts: { name: string; url: string }[] = [];
  let idx = 0;
  let votes: number[] = [];
  let busy = false;
  let starting = false;
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

  // Create the game as soon as the operator commits to playing, so it shows up
  // as an active game (admin portal) through the record-the-original step —
  // not only once the first take is reversed.
  async function start() {
    if (!canStart || starting) return;
    starting = true;
    err = "";
    try {
      names = clean;
      code = (await createSolo()).code;
      step = "original";
    } catch (x) {
      err = x instanceof Error ? x.message : String(x);
    } finally {
      starting = false;
    }
  }

  async function onOriginal(e: CustomEvent<{ recording: Recording }>) {
    if (!code) return;
    busy = true;
    err = "";
    try {
      const r = await uploadOriginal(code, "", e.detail.recording);
      originalUrl = r.url;
      originalForwardUrl = r.forwardUrl;
      step = "listen";
    } catch (x) {
      err = x instanceof Error ? x.message : String(x);
    } finally {
      busy = false;
    }
  }

  async function onPickSong(e: CustomEvent<{ slug: string }>) {
    if (!code) return;
    busy = true;
    err = "";
    try {
      const r = await pickOriginalFromLibrary(code, e.detail.slug);
      originalUrl = r.url;
      originalForwardUrl = r.forwardUrl;
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

  function bump(i: number, delta: number) {
    votes = votes.map((v, j) => (j === i ? Math.max(0, v + delta) : v));
  }

  $: topVotes = Math.max(0, ...votes);
  $: leaders = attempts.filter((_, i) => topVotes > 0 && votes[i] === topVotes);

  function clearRound() {
    originalUrl = "";
    originalForwardUrl = "";
    attempts = [];
    idx = 0;
    votes = [];
    err = "";
  }

  async function playAgain() {
    let next: string;
    try {
      next = (await createSolo()).code;
    } catch (x) {
      err = x instanceof Error ? x.message : String(x);
      return; // stay on the reveal screen
    }
    clearRound();
    code = next;
    step = "original";
  }

  function newGame() {
    names = ["", ""];
    code = "";
    clearRound();
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
      <button on:click={start} disabled={!canStart || starting}>
        {starting ? "Starting…" : "Start"}
      </button>
      {#if err}<span class="err">{err}</span>{/if}

      <PrivacyNote />
    </div>
  {:else if step === "original"}
    <div class="panel">
      <h2>Record the song</h2>
      <p>Sing a line or two. Everyone else will hear it backwards.</p>
      <RecordControl {busy} useLabel="Reverse it" on:done={onOriginal} />
      <SongPicker {busy} on:pick={onPickSong} />
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
              <div class="votes">
                <button class="secondary vbtn" on:click={() => bump(i, -1)} disabled={!votes[i]}>
                  −
                </button>
                <span class="vcount">{votes[i]} {votes[i] === 1 ? "vote" : "votes"}</span>
                <button class="secondary vbtn" on:click={() => bump(i, 1)}>+</button>
              </div>
            </div>
            <PlayClip url={a.url} />
          </div>
        {/each}
      </div>
      <PlayClip url={originalForwardUrl || originalUrl} label="The original song — how it should sound" />
      {#if leaders.length}
        <p><strong>{leaders.map((l) => l.name).join(", ")}</strong> {leaders.length > 1 ? "tie" : "wins"}!</p>
      {/if}
    </div>
    <div class="row">
      <button on:click={playAgain}>Play again (same players)</button>
      <button class="secondary" on:click={newGame}>New game</button>
    </div>
    {#if err}<span class="err">{err}</span>{/if}
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
  .votes {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .vbtn {
    min-height: 0;
    padding: 4px 12px;
    font-size: 1rem;
    line-height: 1;
  }
  .vcount {
    font-size: 0.8rem;
    color: var(--muted);
    min-width: 4.5em;
    text-align: center;
  }
</style>
