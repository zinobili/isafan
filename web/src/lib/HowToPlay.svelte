<script lang="ts">
  import { onMount } from "svelte";

  // Bump the suffix if the slides change enough to be worth re-showing.
  const SEEN_KEY = "isafan.howToPlay.seen.v1";

  let show = false;
  let i = 0;

  const slides = [
    { n: 1, en: "Someone sings", zh: "有人開唱" },
    { n: 2, en: "We flip the audio", zh: "倒轉聲音" },
    { n: 3, en: "Copy the gibberish", zh: "跟著亂唱" },
    { n: 4, en: "Flip back & vote", zh: "再倒轉、投票" },
  ];
  const last = slides.length - 1;

  onMount(() => {
    try {
      show = localStorage.getItem(SEEN_KEY) == null;
    } catch {
      show = true;
    }
  });

  function dismiss() {
    show = false;
    try {
      localStorage.setItem(SEEN_KEY, "1");
    } catch {
      /* private mode — just close for this session */
    }
  }

  function go(n: number) {
    i = Math.max(0, Math.min(last, n));
  }

  // Swipe as a progressive enhancement; the arrows stay the accessible path.
  function swipe(node: HTMLElement) {
    let x0: number | null = null;
    const start = (x: number) => (x0 = x);
    const end = (x: number) => {
      if (x0 == null) return;
      const dx = x - x0;
      if (dx < -40) go(i + 1);
      else if (dx > 40) go(i - 1);
      x0 = null;
    };
    const ts = (e: TouchEvent) => start(e.touches[0].clientX);
    const te = (e: TouchEvent) => end(e.changedTouches[0].clientX);
    const md = (e: MouseEvent) => start(e.clientX);
    const mu = (e: MouseEvent) => end(e.clientX);
    node.addEventListener("touchstart", ts, { passive: true });
    node.addEventListener("touchend", te);
    node.addEventListener("mousedown", md);
    window.addEventListener("mouseup", mu);
    return {
      destroy() {
        node.removeEventListener("touchstart", ts);
        node.removeEventListener("touchend", te);
        node.removeEventListener("mousedown", md);
        window.removeEventListener("mouseup", mu);
      },
    };
  }
</script>

{#if show}
  <div class="panel htp">
    <div class="htp-head">
      <span class="htp-title">How to play · 玩法</span>
      <button class="htp-skip" on:click={dismiss}>Skip 略過</button>
    </div>

    <div class="htp-view" use:swipe>
      <div class="htp-track" style="transform: translateX({-i * 100}%)">
        <!-- 1 · pig -->
        <div class="htp-slide">
          <p class="htp-h">1 · Someone sings</p>
          <p class="htp-sub">有人開唱</p>
          <div class="htp-art a1">
            <svg viewBox="0 0 150 132" fill="none" aria-hidden="true">
              <g class="note" fill="#BA7517"><path d="M104 46v20a7 7 0 1 1-4-6V42l14-4v6z" /></g>
              <g class="note n2" fill="#EF9F27"><circle cx="38" cy="54" r="6" /><rect x="43" y="32" width="3" height="22" /></g>
              <g class="note n3" fill="#BA7517"><circle cx="120" cy="82" r="5" /><rect x="124" y="64" width="3" height="20" /></g>
              <g class="bob">
                <path d="M44 66 40 46 60 62Z" fill="#F4C0D1" stroke="#4B1528" stroke-width="3" />
                <path d="M88 66 92 46 72 62Z" fill="#F4C0D1" stroke="#4B1528" stroke-width="3" />
                <ellipse cx="66" cy="88" rx="30" ry="28" fill="#F4C0D1" stroke="#4B1528" stroke-width="3.5" />
                <circle cx="56" cy="83" r="4" fill="#4B1528" /><circle cx="76" cy="83" r="4" fill="#4B1528" />
                <ellipse cx="66" cy="97" rx="13" ry="9" fill="#ED93B1" stroke="#4B1528" stroke-width="2.5" />
                <circle cx="62" cy="97" r="2" fill="#4B1528" /><circle cx="70" cy="97" r="2" fill="#4B1528" />
                <line x1="94" y1="92" x2="108" y2="82" stroke="#4B1528" stroke-width="4" stroke-linecap="round" />
                <circle cx="112" cy="79" r="8" fill="#4B1528" />
              </g>
            </svg>
          </div>
          <p class="htp-cap">The host records a short clip — or just picks a ready-made song.</p>
          <p class="htp-cap zh">主持人錄一小段，或者直接選一首現成的歌（將聽到 Zino 優美的歌聲）</p>
        </div>

        <!-- 2 · cassette tape -->
        <div class="htp-slide">
          <p class="htp-h">2 · We flip the audio</p>
          <p class="htp-sub">倒轉聲音</p>
          <div class="htp-art a2">
            <svg viewBox="0 0 160 132" fill="none" aria-hidden="true">
              <g class="spin">
                <path d="M80 20a18 18 0 1 1-13 5.5" stroke="#378ADD" stroke-width="4.5" stroke-linecap="round" />
                <path d="M64 16l5 13-14 2z" fill="#185FA5" />
              </g>
              <g class="bob">
                <rect x="34" y="52" width="92" height="56" rx="11" fill="#85B7EB" stroke="#0C447C" stroke-width="3.5" />
                <circle cx="63" cy="74" r="13" fill="#E6F1FB" stroke="#0C447C" stroke-width="3" />
                <circle cx="97" cy="74" r="13" fill="#E6F1FB" stroke="#0C447C" stroke-width="3" />
                <g class="spin"><circle cx="63" cy="74" r="4" fill="#0C447C" /><g stroke="#0C447C" stroke-width="2.5" stroke-linecap="round"><line x1="63" y1="65" x2="63" y2="69" /><line x1="63" y1="79" x2="63" y2="83" /><line x1="54" y1="74" x2="58" y2="74" /><line x1="68" y1="74" x2="72" y2="74" /></g></g>
                <g class="spin"><circle cx="97" cy="74" r="4" fill="#0C447C" /><g stroke="#0C447C" stroke-width="2.5" stroke-linecap="round"><line x1="97" y1="65" x2="97" y2="69" /><line x1="97" y1="79" x2="97" y2="83" /><line x1="88" y1="74" x2="92" y2="74" /><line x1="102" y1="74" x2="106" y2="74" /></g></g>
                <path d="M66 94q14 9 28 0" stroke="#0C447C" stroke-width="3.5" stroke-linecap="round" />
                <rect x="48" y="108" width="12" height="6" rx="2" fill="#0C447C" />
                <rect x="100" y="108" width="12" height="6" rx="2" fill="#0C447C" />
              </g>
            </svg>
          </div>
          <p class="htp-cap">We play the audio backwards. It comes out sounding like pure gibberish.</p>
          <p class="htp-cap zh">我們會把聲音倒轉播放，聽起來就像一團亂碼 ×&amp;…%￥</p>
        </div>

        <!-- 3 · three off-key cats -->
        <div class="htp-slide">
          <p class="htp-h">3 · Copy the gibberish</p>
          <p class="htp-sub">跟著亂唱</p>
          <div class="htp-art a3">
            <svg viewBox="0 0 210 132" fill="none" aria-hidden="true">
              <g class="bob">
                <g stroke="#993C1D" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" fill="none">
                  <path d="M46 34l-4 5 5 3-4 5" /><path d="M46 34q7 1 4 8" />
                </g>
                <ellipse cx="39" cy="50" rx="5" ry="3.6" fill="#993C1D" transform="rotate(-22 39 50)" />
                <path d="M22 64 18 46 36 60Z" fill="#FAC775" stroke="#854F0B" stroke-width="2.4" />
                <path d="M56 64 60 46 42 60Z" fill="#FAC775" stroke="#854F0B" stroke-width="2.4" />
                <circle cx="39" cy="82" r="19" fill="#FAC775" stroke="#854F0B" stroke-width="3" />
                <circle cx="33" cy="81" r="2.8" fill="#3A2A06" /><circle cx="45" cy="81" r="2.8" fill="#3A2A06" />
                <path d="M37 87 41 87 39 90Z" fill="#D85A30" />
                <path d="M39 90q-4 4 -7 1M39 90q4 4 7 1" stroke="#854F0B" stroke-width="1.9" stroke-linecap="round" />
                <g stroke="#854F0B" stroke-width="1.5" stroke-linecap="round"><line x1="29" y1="86" x2="16" y2="84" /><line x1="29" y1="89" x2="16" y2="92" /><line x1="49" y1="86" x2="62" y2="84" /><line x1="49" y1="89" x2="62" y2="92" /></g>
              </g>
              <g class="bob b2">
                <g stroke="#993C1D" stroke-width="2.4" stroke-linecap="round" fill="none">
                  <path d="M96 26q10 9 19 -1" /><path d="M96 26v12" /><path d="M115 25v14" />
                </g>
                <ellipse cx="93" cy="40" rx="4.6" ry="3.4" fill="#993C1D" transform="rotate(12 93 40)" />
                <ellipse cx="118" cy="41" rx="4.6" ry="3.4" fill="#993C1D" transform="rotate(-12 118 41)" />
                <path d="M86 58 82 38 100 54Z" fill="#FAC775" stroke="#854F0B" stroke-width="2.6" />
                <path d="M124 58 128 38 110 54Z" fill="#FAC775" stroke="#854F0B" stroke-width="2.6" />
                <circle cx="105" cy="78" r="22" fill="#FAC775" stroke="#854F0B" stroke-width="3.2" />
                <circle cx="98" cy="77" r="3.2" fill="#3A2A06" /><circle cx="112" cy="77" r="3.2" fill="#3A2A06" />
                <path d="M102 84 108 84 105 88Z" fill="#D85A30" />
                <path d="M105 88q-5 5 -8 1M105 88q5 5 8 1" stroke="#854F0B" stroke-width="2.1" stroke-linecap="round" />
                <g stroke="#854F0B" stroke-width="1.6" stroke-linecap="round"><line x1="93" y1="82" x2="78" y2="80" /><line x1="93" y1="86" x2="78" y2="89" /><line x1="117" y1="82" x2="132" y2="80" /><line x1="117" y1="86" x2="132" y2="89" /></g>
              </g>
              <g class="bob b3">
                <g stroke="#993C1D" stroke-width="2.4" stroke-linecap="round" fill="none">
                  <path d="M172 34c-2 5 6 6 4 11c-1 3 -6 3 -6 0" />
                </g>
                <ellipse cx="168" cy="50" rx="5" ry="3.6" fill="#993C1D" transform="rotate(16 168 50)" />
                <path d="M154 64 150 46 168 60Z" fill="#FAC775" stroke="#854F0B" stroke-width="2.4" />
                <path d="M188 64 192 46 174 60Z" fill="#FAC775" stroke="#854F0B" stroke-width="2.4" />
                <circle cx="171" cy="82" r="19" fill="#FAC775" stroke="#854F0B" stroke-width="3" />
                <circle cx="165" cy="81" r="2.8" fill="#3A2A06" /><circle cx="177" cy="81" r="2.8" fill="#3A2A06" />
                <path d="M169 87 173 87 171 90Z" fill="#D85A30" />
                <path d="M171 90q-4 4 -7 1M171 90q4 4 7 1" stroke="#854F0B" stroke-width="1.9" stroke-linecap="round" />
                <g stroke="#854F0B" stroke-width="1.5" stroke-linecap="round"><line x1="161" y1="86" x2="148" y2="84" /><line x1="161" y1="89" x2="148" y2="92" /><line x1="181" y1="86" x2="194" y2="84" /><line x1="181" y1="89" x2="194" y2="92" /></g>
              </g>
            </svg>
          </div>
          <p class="htp-cap">Listen to that gibberish-sounding clip and try to sing it back.</p>
          <p class="htp-cap zh">聽聽那段亂碼一般的歌聲，試試照著唱回去～</p>
        </div>

        <!-- 4 · dog + trophy -->
        <div class="htp-slide">
          <p class="htp-h">4 · Flip back &amp; vote</p>
          <p class="htp-sub">再倒轉、投票</p>
          <div class="htp-art a4">
            <svg viewBox="0 0 150 132" fill="none" aria-hidden="true">
              <rect class="conf" x="34" y="12" width="8" height="8" rx="2" fill="#ED93B1" />
              <rect class="conf c2" x="72" y="8" width="8" height="8" rx="2" fill="#EF9F27" />
              <rect class="conf c3" x="106" y="14" width="8" height="8" rx="2" fill="#5DCAA5" />
              <rect class="conf c4" x="52" y="10" width="8" height="8" rx="2" fill="#85B7EB" />
              <g class="wiggle">
                <path d="M62 30h26v11a13 13 0 0 1-26 0z" fill="#FAC775" stroke="#633806" stroke-width="3" />
                <path d="M62 33h-7a7 7 0 0 0 7 9M88 33h7a7 7 0 0 1-7 9" stroke="#633806" stroke-width="3" />
                <path d="M69 35l4 4 8-8" stroke="#633806" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
                <line x1="75" y1="54" x2="75" y2="61" stroke="#633806" stroke-width="4" />
                <rect x="66" y="61" width="18" height="6" rx="2" fill="#633806" />
              </g>
              <g class="bob">
                <ellipse cx="50" cy="102" rx="10" ry="19" fill="#854F0B" />
                <ellipse cx="100" cy="102" rx="10" ry="19" fill="#854F0B" />
                <circle cx="75" cy="100" r="26" fill="#FAC775" stroke="#633806" stroke-width="3.5" />
                <circle cx="66" cy="98" r="3.8" fill="#3A2205" /><circle cx="84" cy="98" r="3.8" fill="#3A2205" />
                <ellipse cx="75" cy="110" rx="14" ry="10" fill="#FAEEDA" stroke="#633806" stroke-width="2.5" />
                <ellipse cx="75" cy="105" rx="4" ry="3" fill="#2C1A03" />
                <path d="M75 108q-6 4 -10 2M75 108q6 4 10 2" stroke="#633806" stroke-width="2.5" stroke-linecap="round" />
                <path d="M73 116q-3 9 1 11q4 -3 1 -11z" fill="#ED93B1" stroke="#4B1528" stroke-width="1.5" />
              </g>
            </svg>
          </div>
          <p class="htp-cap">Finally we reverse every recording once more — then everyone votes for the closest match.</p>
          <p class="htp-cap zh">最後我們會把所有錄音倒轉一次，大家投票選最像的那個～</p>
        </div>
      </div>
    </div>

    <div class="htp-foot">
      <button
        class="secondary htp-nav"
        on:click={() => go(i - 1)}
        disabled={i === 0}
        aria-label="Previous slide"
      >‹</button>

      <div class="htp-dots">
        {#each slides as s, k}
          <button
            class="htp-dot"
            class:on={k === i}
            aria-label={`Go to slide ${k + 1}`}
            aria-current={k === i}
            on:click={() => go(k)}
          >{s.n}</button>
        {/each}
      </div>

      <button class="htp-next" on:click={() => (i === last ? dismiss() : go(i + 1))}>
        {i === last ? "Got it 開始" : "Next 下一步"}
      </button>
    </div>
  </div>
{/if}

<style>
  .htp {
    gap: 12px;
    overflow: hidden;
  }

  .htp-head {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .htp-title {
    font-weight: 600;
    font-size: 0.95rem;
  }
  .htp-skip {
    margin-left: auto;
    background: transparent;
    border: 0;
    color: var(--muted);
    font-weight: 500;
    font-size: 0.8rem;
    padding: 4px 6px;
    min-height: 0;
  }

  .htp-view {
    overflow: hidden;
    margin: 0 -18px;
    touch-action: pan-y;
    cursor: grab;
  }
  .htp-view:active {
    cursor: grabbing;
  }
  .htp-track {
    display: flex;
    transition: transform 0.28s ease;
  }
  .htp-slide {
    flex: 0 0 100%;
    padding: 0 18px;
  }

  .htp-h {
    margin: 0 0 2px;
    text-align: center;
    color: var(--text);
    font-weight: 600;
    font-size: 0.98rem;
  }
  .htp-sub {
    margin: 0 0 10px;
    text-align: center;
    color: var(--muted);
    font-size: 0.78rem;
  }

  .htp-art {
    border-radius: 12px;
    height: 150px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .htp-art svg {
    height: 130px;
    width: auto;
  }
  .a1 { background: #ffe9ef; }
  .a2 { background: #fff1d8; }
  .a3 { background: #fdeecb; }
  .a4 { background: #ffe6ee; }

  .htp-cap {
    margin: 10px 0 0;
    text-align: center;
    color: var(--text);
    font-size: 0.85rem;
    line-height: 1.5;
  }
  .htp-cap.zh {
    margin-top: 3px;
    color: var(--muted);
    font-size: 0.8rem;
    line-height: 1.65;
  }

  .htp-foot {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .htp-nav {
    min-height: 0;
    padding: 6px 12px;
    font-size: 1rem;
    line-height: 1;
  }
  .htp-dots {
    display: flex;
    gap: 6px;
    margin: 0 auto;
  }
  .htp-dot {
    width: 22px;
    height: 22px;
    min-height: 0;
    padding: 0;
    border-radius: 999px;
    background: var(--panel-2);
    color: var(--muted);
    font-size: 0.72rem;
    font-weight: 600;
  }
  .htp-dot.on {
    background: color-mix(in srgb, var(--accent) 40%, transparent);
    color: var(--text);
  }
  .htp-next {
    min-height: 0;
    padding: 8px 14px;
    font-size: 0.82rem;
  }

  .bob { animation: htp-bob 2.2s ease-in-out infinite; transform-box: fill-box; transform-origin: center; }
  .b2 { animation-delay: 0.35s; }
  .b3 { animation-delay: 0.7s; }
  .spin { animation: htp-spin 3.2s linear infinite; transform-box: fill-box; transform-origin: center; }
  .wiggle { animation: htp-wiggle 1.8s ease-in-out infinite; transform-box: fill-box; transform-origin: bottom center; }
  .note { animation: htp-float 2.4s ease-in infinite; }
  .n2 { animation-delay: 0.8s; }
  .n3 { animation-delay: 1.6s; }
  .conf { animation: htp-fall 2.6s linear infinite; }
  .c2 { animation-delay: 0.5s; }
  .c3 { animation-delay: 1s; }
  .c4 { animation-delay: 1.6s; }

  @keyframes htp-bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-6px); } }
  @keyframes htp-spin { to { transform: rotate(360deg); } }
  @keyframes htp-wiggle { 0%, 100% { transform: rotate(-5deg); } 50% { transform: rotate(5deg); } }
  @keyframes htp-float {
    0% { transform: translateY(6px); opacity: 0; }
    25% { opacity: 1; }
    100% { transform: translateY(-34px); opacity: 0; }
  }
  @keyframes htp-fall {
    0% { transform: translateY(-16px) rotate(0); opacity: 0; }
    20% { opacity: 1; }
    100% { transform: translateY(58px) rotate(220deg); opacity: 0; }
  }

  @media (prefers-reduced-motion: reduce) {
    .htp-track { transition: none; }
    .bob, .spin, .wiggle, .note, .conf { animation: none; }
    .note { opacity: 1; }
    .conf { opacity: 0; }
  }
</style>
