/**
 * Client-side mirror of app/uploads.py.
 *
 * This exists to save a worker a round trip and to give them the reason before
 * they tap upload — the server re-runs every one of these checks and is the only
 * thing that actually decides whether a file is accepted. A client that can be
 * fooled is fine here precisely because it is not trusted.
 */
import { UPLOAD_ACCEPT, UPLOAD_MAX_BYTES, UPLOAD_MAX_BYTES_LABEL } from "../api";

const ALLOWED = UPLOAD_ACCEPT.split(",");

/** A rejection reason to show the worker, or null if the file looks acceptable. */
export function validateDocumentFile(file: File): string | null {
  const dot = file.name.lastIndexOf(".");
  const ext = dot > 0 ? file.name.slice(dot).toLowerCase() : "";
  if (!ALLOWED.includes(ext)) {
    return `Choose a PDF, JPG or PNG file. “${file.name}” is not one.`;
  }
  if (file.size === 0) {
    return "That file is empty. Choose it again and check it opens on your phone.";
  }
  if (file.size > UPLOAD_MAX_BYTES) {
    const size = file.size >= 1024 * 1024
      ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
      : `${Math.round(file.size / 1024)} KB`;
    return `That file is ${size}, over the ${UPLOAD_MAX_BYTES_LABEL} limit. Photograph the document again, or save it as a smaller PDF.`;
  }
  return null;
}

/** A short human label for a chosen file, e.g. "aadhaar.pdf · 1.2 MB". */
export function describeFile(file: File): string {
  const size = file.size >= 1024 * 1024
    ? `${(file.size / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(file.size / 1024))} KB`;
  return `${file.name} · ${size}`;
}
