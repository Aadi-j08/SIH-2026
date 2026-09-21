import { useEffect, useRef, useState } from "react";
import { Camera, Clock, Cross, MapPin } from "./Icons";

export type PhotoProofMode = "start" | "end";

interface PhotoProofModalProps {
  mode: PhotoProofMode;
  onClose: () => void;
  onSubmit: (dataUri: string, lat: number, lng: number, timestamp: string) => Promise<void>;
}

export function PhotoProofModal({ mode, onClose, onSubmit }: PhotoProofModalProps) {
  const [photoUri, setPhotoUri] = useState<string | null>(null);
  const [location, setLocation] = useState<{ lat: number; lng: number } | null>(null);
  const [locError, setLocError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [timestampStr] = useState<string>(() =>
    new Date().toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })
  );
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Request location on mount
  useEffect(() => {
    if (!navigator.geolocation) {
      setLocError("Location is not supported by your browser.");
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setLocError(null);
      },
      () => {
        setLocError("Location permission is required to verify your job location.");
      },
      { enableHighAccuracy: true, maximumAge: 0 }
    );
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    // Client-side compression using Canvas
    const reader = new FileReader();
    reader.onload = (event) => {
      const img = new Image();
      img.onload = () => {
        const canvas = document.createElement("canvas");
        const MAX_WIDTH = 1200;
        const MAX_HEIGHT = 1200;
        let width = img.width;
        let height = img.height;

        if (width > height) {
          if (width > MAX_WIDTH) {
            height *= MAX_WIDTH / width;
            width = MAX_WIDTH;
          }
        } else {
          if (height > MAX_HEIGHT) {
            width *= MAX_HEIGHT / height;
            height = MAX_HEIGHT;
          }
        }

        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        if (ctx) {
          ctx.drawImage(img, 0, 0, width, height);
          setPhotoUri(canvas.toDataURL("image/jpeg", 0.7)); // Compress to 70% quality JPEG
        }
      };
      if (event.target?.result) {
        img.src = event.target.result as string;
      }
    };
    reader.readAsDataURL(file);
  };

  const submit = async () => {
    if (!photoUri) {
      setError("Please take a photo first.");
      return;
    }
    if (!location) {
      setError("Location permission is required to submit job proof.");
      return;
    }

    setBusy(true);
    setError(null);
    try {
      const timestamp = new Date().toISOString();
      await onSubmit(photoUri, location.lat, location.lng, timestamp);
      onClose(); // only close on success
    } catch (err: any) {
      setError(err.message || "Failed to submit proof. Please try again.");
      setBusy(false);
    }
  };

  const title = mode === "start" ? "Start Job Verification" : "Work Completion Verification";
  const desc =
    mode === "start"
      ? "Please take a selfie or a photo of the site to prove you have arrived."
      : "Please capture a photo of the completed repair.";

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        backgroundColor: "rgba(0, 0, 0, 0.65)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 9999,
        padding: 16,
        boxSizing: "border-box",
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) onClose();
      }}
    >
      <div
        className="sheet"
        style={{
          width: "100%",
          maxWidth: 420,
          maxHeight: "90vh",
          overflowY: "auto",
          background: "var(--white)",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.25)",
          borderRadius: "var(--radius-xl)",
          boxSizing: "border-box",
        }}
      >
        <div className="row between">
          <div className="display" style={{ fontSize: 18, fontWeight: 700 }}>
            {title}
          </div>
          <button
            type="button"
            className="btn outline"
            style={{ padding: 4, minHeight: "auto" }}
            onClick={onClose}
            disabled={busy}
            aria-label="Close"
          >
            <Cross size={20} />
          </button>
        </div>

        <div className="muted small">{desc}</div>

        <div className="stack" style={{ gap: 14 }}>
          {photoUri ? (
            <div style={{ position: "relative", borderRadius: 8, overflow: "hidden", background: "#000" }}>
              <img
                src={photoUri}
                alt="Proof preview"
                style={{ width: "100%", maxHeight: 260, objectFit: "contain", display: "block" }}
              />
              <button
                type="button"
                className="btn soft"
                style={{ position: "absolute", bottom: 8, right: 8 }}
                onClick={() => {
                  setPhotoUri(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                disabled={busy}
              >
                Retake
              </button>
            </div>
          ) : (
            <button
              type="button"
              className="btn outline"
              style={{ minHeight: 120, borderStyle: "dashed" }}
              onClick={() => fileInputRef.current?.click()}
            >
              <div className="stack center" style={{ gap: 8 }}>
                <Camera size={32} />
                <div style={{ fontWeight: 600 }}>
                  {mode === "start" ? "📸 Take Arrival Photo / Selfie" : "📸 Capture completed repair"}
                </div>
              </div>
            </button>
          )}

          <input
            type="file"
            accept="image/*"
            capture="environment"
            ref={fileInputRef}
            style={{ display: "none" }}
            onChange={handleFileChange}
          />

          <div className="row" style={{ gap: 8, color: location ? "var(--green-d)" : "var(--red)" }}>
            <MapPin size={18} />
            <div className="small">
              {location
                ? `📍 Location: ${location.lat.toFixed(5)}, ${location.lng.toFixed(5)}`
                : locError || "Acquiring GPS location..."}
            </div>
          </div>

          <div className="row" style={{ gap: 8, color: "var(--ink-2)" }}>
            <Clock size={18} />
            <div className="small">🕒 Timestamp: {timestampStr}</div>
          </div>

          {error && <div className="notice error">{error}</div>}

          <div className="row" style={{ gap: 8, marginTop: 4 }}>
            {photoUri && (
              <button
                type="button"
                className="btn outline"
                style={{ minWidth: 80 }}
                onClick={() => {
                  setPhotoUri(null);
                  if (fileInputRef.current) fileInputRef.current.value = "";
                }}
                disabled={busy}
              >
                Retake
              </button>
            )}
            <button
              type="button"
              className="btn green grow"
              onClick={submit}
              disabled={busy || !photoUri || !location}
            >
              {busy
                ? "Submitting..."
                : mode === "start"
                ? "Submit Start Proof"
                : "Submit Completion Proof"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
