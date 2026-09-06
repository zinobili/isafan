/** Microphone capture (MediaRecorder) + simple clip playback. */

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/aac",
  "audio/ogg;codecs=opus",
];

export function pickMimeType(): string | undefined {
  const MR = window.MediaRecorder;
  if (!MR || !MR.isTypeSupported) return undefined;
  return MIME_CANDIDATES.find((t) => MR.isTypeSupported(t));
}

export function micSupported(): boolean {
  return (
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof window.MediaRecorder === "function"
  );
}

export function extForMime(mime: string): string {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("aac")) return "aac";
  if (mime.includes("ogg")) return "ogg";
  return "bin";
}

export type Recording = { blob: Blob; mime: string; ext: string };

/**
 * Start recording. Resolves with a handle exposing `stop()`; call it to end the
 * take and get the encoded blob. Rejects if the mic is unavailable or denied
 * (e.g. page not served over HTTPS).
 */
export async function startRecording(opts: { onActive?: () => void } = {}): Promise<{
  stop: () => Promise<Recording>;
  cancel: () => void;
}> {
  if (!micSupported()) {
    throw new Error(
      "Microphone recording needs a secure page (HTTPS) and a supported browser."
    );
  }
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
  });

  const mime = pickMimeType();
  const rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
  const chunks: BlobPart[] = [];
  let active = false;
  rec.ondataavailable = (e) => {
    if (e.data && e.data.size) chunks.push(e.data);
    if (!active) {
      active = true;
      opts.onActive?.(); // first bytes are flowing — safe to start a visible timer
    }
  };
  // Timeslice: Chrome/Firefox flush ~every 250ms. This trims the encoder warm-up
  // gap and lets callers align their timer with audio that's actually captured.
  rec.start(250);

  const teardown = () => stream.getTracks().forEach((t) => t.stop());

  return {
    stop: () =>
      new Promise<Recording>((resolve) => {
        rec.onstop = () => {
          teardown();
          const type = rec.mimeType || mime || "audio/webm";
          resolve({ blob: new Blob(chunks, { type }), mime: type, ext: extForMime(type) });
        };
        rec.stop();
      }),
    cancel: () => {
      try {
        rec.stop();
      } catch {
        /* already stopped */
      }
      teardown();
    },
  };
}

/** Play a URL to completion; resolves when it ends (or rejects on error). */
export function playUrl(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const el = new Audio(url);
    el.onended = () => resolve();
    el.onerror = () => reject(new Error("could not play the clip"));
    el.play().catch(reject);
  });
}
