/** Microphone capture via MediaRecorder. */

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/aac",
  "audio/ogg;codecs=opus",
];

function pickMimeType(): string | undefined {
  const MR = window.MediaRecorder;
  if (!MR || !MR.isTypeSupported) return undefined;
  return MIME_CANDIDATES.find((t) => MR.isTypeSupported(t));
}

function extForMime(mime: string): string {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("mp4")) return "mp4";
  if (mime.includes("aac")) return "aac";
  if (mime.includes("ogg")) return "ogg";
  return "bin";
}

export function micSupported(): boolean {
  return (
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof window.MediaRecorder === "function"
  );
}

export type Recording = { blob: Blob; mime: string; ext: string };

/**
 * Start recording. Resolves with a handle: `stop()` ends the take and returns
 * the encoded blob, `cancel()` discards it. Rejects if the mic is unavailable
 * or denied (e.g. the page isn't served over HTTPS). `onActive` fires once the
 * first audio bytes are flowing, so callers can start a timer aligned to real
 * captured audio rather than the encoder warm-up.
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
      opts.onActive?.();
    }
  };
  rec.start(250); // timeslice: flush ~every 250ms so onActive fires promptly

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
