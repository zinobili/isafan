/** Microphone capture via MediaRecorder, with a file-input fallback for pages
 *  served over plain http:// (where getUserMedia is blocked). */

const MIME_CANDIDATES = [
  "audio/webm;codecs=opus",
  "audio/webm",
  "audio/mp4",
  "audio/aac",
  "audio/ogg;codecs=opus",
];

const AUDIO_EXTS = [
  "webm", "mp4", "m4a", "aac", "ogg", "oga", "opus",
  "mp3", "wav", "caf", "amr", "3gp", "3gpp",
];

function pickMimeType(): string | undefined {
  const MR = window.MediaRecorder;
  if (!MR || !MR.isTypeSupported) return undefined;
  return MIME_CANDIDATES.find((t) => MR.isTypeSupported(t));
}

function extForMime(mime: string): string {
  const m = mime.toLowerCase();
  if (m.includes("webm")) return "webm";
  if (m.includes("m4a")) return "m4a";
  if (m.includes("mp4")) return "mp4";
  if (m.includes("aac")) return "aac";
  if (m.includes("ogg") || m.includes("opus")) return "ogg";
  if (m.includes("mpeg") || m.includes("mp3")) return "mp3";
  if (m.includes("wav")) return "wav";
  if (m.includes("3gpp")) return "3gp";
  if (m.includes("amr")) return "amr";
  if (m.includes("caf")) return "caf";
  return "bin";
}

function extForFile(file: File): string {
  const dot = file.name.lastIndexOf(".");
  const suffix = dot >= 0 ? file.name.slice(dot + 1).toLowerCase() : "";
  if (AUDIO_EXTS.includes(suffix)) return suffix === "3gpp" ? "3gp" : suffix;
  return extForMime(file.type || "");
}

export function micSupported(): boolean {
  return (
    typeof navigator.mediaDevices?.getUserMedia === "function" &&
    typeof window.MediaRecorder === "function"
  );
}

/** In-browser recording needs a supported MediaRecorder AND a secure context
 *  (HTTPS or localhost). On plain http://<LAN-IP> the mic is blocked, so
 *  callers fall back to a file input (`recordingFromFile`). */
export function canRecordInline(): boolean {
  return micSupported() && window.isSecureContext === true;
}

export type Recording = { blob: Blob; mime: string; ext: string };

/** Wrap a user-picked audio file (from `<input type="file" accept="audio/*">`)
 *  as a Recording, so the fallback feeds the same upload path as a live take. */
export function recordingFromFile(file: File): Recording {
  return {
    blob: file,
    mime: file.type || "application/octet-stream",
    ext: extForFile(file),
  };
}

/**
 * Start recording. Resolves with a handle: `stop()` ends the take and returns
 * the encoded blob, `cancel()` discards it. Rejects if the mic is unavailable
 * or denied. `onActive` fires once the first audio bytes are flowing, so
 * callers can start a timer aligned to real captured audio rather than the
 * encoder warm-up.
 */
export async function startRecording(opts: { onActive?: () => void } = {}): Promise<{
  stop: () => Promise<Recording>;
  cancel: () => void;
}> {
  if (!canRecordInline()) {
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
