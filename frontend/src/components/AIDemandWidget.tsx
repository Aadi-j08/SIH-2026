import { useEffect, useState } from "react";
import { api, formatRupees } from "../api";

export function AIDemandWidget() {
  const [trade, setTrade] = useState("plumbing");
  const [forecast, setForecast] = useState<any>(null);
  const [dispatching, setDispatching] = useState(false);
  const [dispatchResult, setDispatchResult] = useState<any>(null);

  useEffect(() => {
    fetchForecast(trade);
  }, [trade]);

  const fetchForecast = async (t: string) => {
    try {
      const data = await api.forecastML(t, "Bhopal Central");
      setForecast(data);
    } catch (err) {
      console.error("Failed to load ML forecast:", err);
    }
  };

  const handleBatchDispatch = async () => {
    setDispatching(true);
    try {
      const res = await api.allocation.batchDispatch(25.0);
      setDispatchResult(res);
    } catch (err) {
      console.error("Batch dispatch failed:", err);
    } finally {
      setDispatching(false);
    }
  };

  return (
    <div style={{
      background: "#fff",
      border: "1px solid #e2ddd5",
      borderRadius: "16px",
      padding: "20px 24px",
      marginBottom: "24px",
      boxShadow: "0 4px 18px rgba(0,0,0,0.02)"
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px", flexWrap: "wrap", gap: "10px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span style={{ fontSize: "1.2rem" }}>📈</span>
            <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 700 }}>
              AI Demand Forecasting & Dynamic Fair Pricing (Ridge ML)
            </h3>
          </div>
          <p style={{ margin: "4px 0 0 0", fontSize: "0.85rem", color: "#666" }}>
            7-day forward predictive volume and cooperative minimum wage floors per trade.
          </p>
        </div>

        <div style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <select
            value={trade}
            onChange={(e) => setTrade(e.target.value)}
            style={{
              padding: "8px 12px",
              borderRadius: "8px",
              border: "1px solid #ccc",
              fontWeight: 600,
              fontSize: "0.88rem",
              background: "#faf8f5"
            }}
          >
            <option value="plumbing">Plumbing</option>
            <option value="electrician">Electrician</option>
            <option value="carpentry">Carpentry</option>
            <option value="painting">Painting</option>
            <option value="masonry">Masonry</option>
            <option value="appliance">Appliance Repair</option>
          </select>

          <button
            type="button"
            onClick={handleBatchDispatch}
            disabled={dispatching}
            style={{
              padding: "8px 16px",
              borderRadius: "8px",
              background: "var(--indigo, #5E78D9)",
              color: "#fff",
              border: "none",
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px"
            }}
          >
            {dispatching ? "Solving..." : "⚡ Run Fair Batch Dispatch"}
          </button>
        </div>
      </div>

      {dispatchResult && (
        <div style={{
          background: "rgba(37, 152, 77, 0.08)",
          border: "1px solid rgba(37, 152, 77, 0.25)",
          borderRadius: "10px",
          padding: "12px 16px",
          marginBottom: "16px",
          fontSize: "0.88rem"
        }}>
          <strong>⚖️ Fair Batch Allocation Solved:</strong> {dispatchResult.cooperative_fairness_summary}
          <div style={{ marginTop: "6px", fontSize: "0.82rem", color: "#444" }}>
            Matched <b>{dispatchResult.matched_count}</b> jobs with zero idle worker bias.
          </div>
        </div>
      )}

      {forecast && (
        <>
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(130px, 1fr))",
            gap: "10px",
            marginBottom: "14px"
          }}>
            {forecast.daily_forecast.map((day: any, idx: number) => (
              <div
                key={idx}
                style={{
                  background: day.is_weekend ? "rgba(198, 93, 38, 0.06)" : "#faf8f5",
                  border: day.is_weekend ? "1px solid rgba(198, 93, 38, 0.25)" : "1px solid #e8e3dc",
                  borderRadius: "10px",
                  padding: "10px 12px",
                  textAlign: "center"
                }}
              >
                <div style={{ fontSize: "0.78rem", fontWeight: 700, color: day.is_weekend ? "var(--terracotta-d)" : "#555" }}>
                  {day.day_name.slice(0, 3)} ({day.date.slice(5)})
                </div>
                <div style={{ fontSize: "1.25rem", fontWeight: 800, margin: "4px 0", color: "#222" }}>
                  {day.predicted_bookings} <span style={{ fontSize: "0.7rem", fontWeight: 500 }}>jobs</span>
                </div>
                <div style={{ fontSize: "0.75rem", color: "#777" }}>
                  Rate: <b>{formatRupees(day.recommended_rate_inr)}</b>
                </div>
                <div style={{ fontSize: "0.7rem", color: "#999" }}>
                  Floor: {formatRupees(day.floor_rate_inr)}
                </div>
              </div>
            ))}
          </div>

          <div style={{ fontSize: "0.85rem", color: "#555", background: "#f5f3ef", padding: "10px 14px", borderRadius: "8px" }}>
            💡 <b>Cooperative Planning Insight:</b> {forecast.insights}
          </div>
        </>
      )}
    </div>
  );
}
