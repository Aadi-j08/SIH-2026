import { useEffect, useState } from "react";

import { type Feedback, api, errorMessage } from "../../api";
import { Refresh, Star } from "../../components/Icons";

const TYPE_LABELS: Record<Feedback["type"], string> = {
  bug: "Bug Report",
  feature: "Feature Request",
  general: "General Feedback",
};

const TYPE_COLORS: Record<Feedback["type"], string> = {
  bug: "var(--red, #d32f2f)",
  feature: "var(--indigo)",
  general: "var(--green)",
};

export default function FeedbackPage() {
  const [items, setItems] = useState<Feedback[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "unresolved" | "resolved">("all");

  const load = async () => {
    setLoading(true);
    try {
      const resolved = filter === "all" ? undefined : filter === "resolved";
      setItems(await api.feedback.list(undefined, resolved));
      setError(null);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [filter]);

  const stats = {
    total: items.length,
    bugs: items.filter((f) => f.type === "bug" && !f.resolved).length,
    features: items.filter((f) => f.type === "feature" && !f.resolved).length,
  };

  return (
    <div className="sabha-page" style={{ padding: "24px 0" }}>
      <div className="row" style={{ gap: 12, alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
        <h1 style={{ margin: 0, fontSize: 24, fontWeight: 700 }}>User Feedback</h1>
        <button type="button" className="btn outline small" onClick={load} disabled={loading}>
          <Refresh size={16} /> {loading ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <div className="row" style={{ gap: 8, marginBottom: 20 }}>
        <button
          type="button"
          className={filter === "all" ? "btn primary small" : "btn outline small"}
          onClick={() => setFilter("all")}
        >
          All ({stats.total})
        </button>
        <button
          type="button"
          className={filter === "unresolved" ? "btn primary small" : "btn outline small"}
          onClick={() => setFilter("unresolved")}
        >
          Unresolved ({stats.bugs + stats.features})
        </button>
        <button
          type="button"
          className={filter === "resolved" ? "btn primary small" : "btn outline small"}
          onClick={() => setFilter("resolved")}
        >
          Resolved
        </button>
      </div>

      {error && <p style={{ color: "var(--red, #d32f2f)" }}>{error}</p>}

      {items.length === 0 ? (
        <p className="small muted" style={{ padding: "32px 0", textAlign: "center" }}>
          {filter === "all" ? "No feedback yet." : `No ${filter} feedback.`}
        </p>
      ) : (
        <div className="stack" style={{ gap: 12 }}>
          {items.map((f) => (
            <div key={f.id} className="panel" style={{ padding: 16, borderRadius: "var(--radius)" }}>
              <div className="row" style={{ gap: 10, alignItems: "center", justifyContent: "space-between" }}>
                <span
                  className="pill"
                  style={{
                    background: f.type === "bug" ? "rgba(211, 47, 47, 0.1)" : f.type === "feature" ? "rgba(94, 120, 217, 0.1)" : "rgba(37, 152, 77, 0.1)",
                    color: TYPE_COLORS[f.type],
                  }}
                >
                  {TYPE_LABELS[f.type]}
                </span>
                <div className="row" style={{ gap: 4 }}>
                  {f.rating !== null &&
                    Array.from({ length: 5 }).map((_, i) => (
                      <Star key={i} size={16} filled={i < (f.rating ?? 0)} />
                    ))}
                </div>
              </div>
              <p style={{ margin: "8px 0", whiteSpace: "pre-wrap" }}>{f.message}</p>
              <div className="row" style={{ gap: 12, justifyContent: "space-between" }}>
                <span className="small muted">
                  {f.user_name ? `${f.user_name} (${f.user_portal})` : "Anonymous"}
                  {f.user_phone && ` · ${f.user_phone}`}
                </span>
                <span className="small muted">{f.created_at}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
