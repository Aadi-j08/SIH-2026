import { useState } from "react";

import { type FeedbackCreate, api, errorMessage } from "../api";
import { MessageCircle, Send, Star, Cross } from "./Icons";

const FEEDBACK_TYPES: { value: FeedbackCreate["type"]; label: string; icon: string }[] = [
  { value: "bug", label: "Bug Report", icon: "🐛" },
  { value: "feature", label: "Feature Request", icon: "💡" },
  { value: "general", label: "General Feedback", icon: "💬" },
];

export default function FeedbackForm({ onSubmitted }: { onSubmitted?: () => void }) {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState<FeedbackCreate["type"]>("general");
  const [rating, setRating] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  if (!open) {
    return (
      <button
        type="button"
        className="feedback-fab"
        onClick={() => setOpen(true)}
        aria-label="Give feedback"
        title="Give feedback"
      >
        <MessageCircle size={22} />
      </button>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await api.feedback.submit({ type, rating, message: message.trim() });
      setSuccess(true);
      setType("general");
      setRating(null);
      setMessage("");
      onSubmitted?.();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="feedback-overlay" onClick={() => !submitting && setOpen(false)}>
      <div
        className="feedback-panel"
        onClick={(e) => e.stopPropagation()}
        aria-modal="true"
        role="dialog"
      >
        <div className="row" style={{ gap: 8, alignItems: "center", justifyContent: "space-between" }}>
          <h3 style={{ margin: 0, fontSize: 20, fontWeight: 700 }}>Send feedback</h3>
        <button type="button" className="icon-btn" onClick={() => setOpen(false)} aria-label="Close">
          <Cross size={18} />
        </button>
        </div>

        {success ? (
          <div className="stack" style={{ gap: 12, padding: "24px 0" }}>
            <div className="pill green" style={{ gap: 6, alignSelf: "flex-start" }}>
              <span>✓</span> Thank you for your feedback!
            </div>
            <button type="button" className="btn outline" onClick={() => setOpen(false)}>
              Close
            </button>
          </div>
        ) : (
          <form className="stack" style={{ gap: 14 }} onSubmit={handleSubmit}>
            <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
              {FEEDBACK_TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  className={type === t.value ? "btn primary small" : "btn outline small"}
                  onClick={() => setType(t.value)}
                  style={{ minWidth: 120 }}
                >
                  <span>{t.icon}</span> {t.label}
                </button>
              ))}
            </div>

            <div className="row" style={{ gap: 6 }} aria-label="Rating">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  onClick={() => setRating(rating === star ? null : star)}
                  aria-label={`${star} star${star > 1 ? "s" : ""}`}
                  style={{ background: "none", border: "none", cursor: "pointer", padding: 0 }}
                >
                  <Star size={22} filled={rating !== null && star <= rating} />
                </button>
              ))}
              {rating === null && <span className="small muted">Optional rating</span>}
            </div>

            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              placeholder="What would make SahakarSetu better for you?"
              rows={4}
              minLength={1}
              maxLength={2000}
              required
              style={{ width: "100%", resize: "vertical", padding: 10, fontSize: 15 }}
            />

            {error && <p className="small" style={{ color: "var(--red, #d32f2f)" }}>{error}</p>}

            <div className="row" style={{ gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="btn outline" onClick={() => setOpen(false)} disabled={submitting}>
                Cancel
              </button>
              <button type="submit" className="btn primary" disabled={submitting || message.trim().length === 0}>
                {submitting ? "Sending…" : "Send"}
                <Send size={16} />
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
