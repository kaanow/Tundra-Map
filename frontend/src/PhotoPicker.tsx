import { useEffect, useRef, useState } from 'react';

/** Longest edge of a captured photo. Phone sensors hand back far more than a
 *  freezer thumbnail needs, and the upload cap is 8 MB. */
const MAX_EDGE = 1600;
const JPEG_QUALITY = 0.9;

type Facing = 'environment' | 'user';

type Props = {
  /** Called with the chosen/captured image, or null when cleared. */
  onPick: (file: File | null) => void;
  /** Existing photo to show when nothing new has been picked. */
  currentUrl?: string | null;
  /** Called when the user removes the existing photo. Omit to hide the button. */
  onRemove?: () => void;
};

function hasCamera(): boolean {
  return !!navigator.mediaDevices?.getUserMedia;
}

export default function PhotoPicker({ onPick, currentUrl, onRemove }: Props) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [starting, setStarting] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [facing, setFacing] = useState<Facing>('environment');

  // The <video> only exists once a stream is set, so it cannot be wired up
  // inside start() — the ref is still null there on the first open. Attach
  // after render instead, and re-attach when flipping swaps the stream.
  useEffect(() => {
    const v = videoRef.current;
    if (v && stream) {
      v.srcObject = stream;
      v.play().catch(() => {});
    }
  }, [stream]);

  // Releases the old stream on flip, and the live one on unmount.
  useEffect(() => () => stream?.getTracks().forEach((t) => t.stop()), [stream]);

  // Revoke object URLs so previews don't leak as the user retakes.
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  async function start(next: Facing = facing) {
    setErr(null);
    setStarting(true);
    try {
      const next_stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: next, width: { ideal: 1920 }, height: { ideal: 1920 } },
        audio: false,
      });
      setFacing(next);
      setStream(next_stream);  // effect above attaches it once the video renders
    } catch (e) {
      // Denied permission, no camera, or a non-HTTPS origin.
      setErr(`Camera unavailable: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setStarting(false);
    }
  }

  function stop() { setStream(null); }

  function shoot() {
    const video = videoRef.current;
    if (!video || !video.videoWidth) return;
    const scale = Math.min(1, MAX_EDGE / Math.max(video.videoWidth, video.videoHeight));
    const w = Math.round(video.videoWidth * scale);
    const h = Math.round(video.videoHeight * scale);
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    canvas.getContext('2d')?.drawImage(video, 0, 0, w, h);
    canvas.toBlob(
      (blob) => {
        if (!blob) { setErr('Could not read that frame — try again.'); return; }
        const file = new File([blob], `photo-${Date.now()}.jpg`, { type: 'image/jpeg' });
        setPreview(URL.createObjectURL(blob));
        onPick(file);
        stop();
      },
      'image/jpeg',
      JPEG_QUALITY,
    );
  }

  function pickFile(f: File | null) {
    setPreview(f ? URL.createObjectURL(f) : null);
    onPick(f);
  }

  function clear() {
    setPreview(null);
    onPick(null);
  }

  const shown = preview ?? currentUrl ?? null;

  if (stream) {
    return (
      <div>
        <video ref={videoRef} playsInline muted autoPlay
               style={{ width: '100%', minHeight: 200, borderRadius: 12, background: '#000',
                        transform: facing === 'user' ? 'scaleX(-1)' : undefined }} />
        <div className="actions" style={{ marginTop: 8 }}>
          <button type="button" onClick={shoot}>Capture</button>
          <button type="button" className="ghost"
                  onClick={() => start(facing === 'environment' ? 'user' : 'environment')}>
            Flip camera
          </button>
          <button type="button" className="ghost" onClick={stop}>Cancel</button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {err && <div className="err">{err}</div>}
      {shown && (
        <img src={shown} alt=""
             style={{ width: '100%', maxHeight: 260, objectFit: 'cover',
                      borderRadius: 12, marginBottom: 8 }} />
      )}
      <div className="actions">
        {hasCamera() && (
          <button type="button" disabled={starting} onClick={() => start()}>
            {starting ? 'Starting camera…' : shown ? 'Retake photo' : 'Take photo'}
          </button>
        )}
        <label className="ghost"
               style={{ textAlign: 'center', cursor: 'pointer', padding: '12px 14px',
                        borderRadius: 8, border: '1px solid var(--line)',
                        background: 'transparent' }}>
          {shown ? 'Choose a different file' : 'Choose a file'}
          <input type="file" accept="image/*" hidden
                 onChange={(e) => pickFile(e.target.files?.[0] ?? null)} />
        </label>
        {preview && (
          <button type="button" className="ghost" onClick={clear}>Discard photo</button>
        )}
        {!preview && currentUrl && onRemove && (
          <button type="button" className="danger" onClick={onRemove}>Remove photo</button>
        )}
      </div>
    </div>
  );
}
