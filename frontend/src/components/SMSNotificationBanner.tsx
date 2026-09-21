import { useState } from "react";

interface SMSAlertProps {
  customerName: string;
  trade: string;
  address?: string | null;
  ward?: string | null;
  urgency?: string;
  onAccept?: () => void;
  onDismiss?: () => void;
}

export default function SMSNotificationBanner({
  customerName,
  trade,
  address,
  ward,
  urgency = "urgent",
  onAccept,
  onDismiss,
}: SMSAlertProps) {
  const [visible, setVisible] = useState(true);

  if (!visible) return null;

  const isUrgent = urgency === "urgent" || urgency === "high";

  return (
    <div
      style={{
        position: "fixed",
        top: 16,
        left: "50%",
        transform: "translateX(-50%)",
        width: "calc(100% - 32px)",
        maxWidth: 420,
        zIndex: 9999,
        background: "linear-gradient(135deg, #1e293b 0%, #0f172a 100%)",
        color: "#f8fafc",
        borderRadius: 16,
        boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.5), 0 8px 10px -6px rgba(0, 0, 0, 0.4)",
        border: `1px solid ${isUrgent ? "rgba(239, 68, 68, 0.4)" : "rgba(34, 197, 94, 0.4)"}`,
        padding: "14px 16px",
        animation: "slideDown 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span
            style={{
              fontSize: 10,
              fontWeight: 800,
              background: isUrgent ? "#ef4444" : "#22c55e",
              color: "#fff",
              padding: "2px 6px",
              borderRadius: 4,
              letterSpacing: "0.5px",
            }}
          >
            {isUrgent ? "🚨 URGENT SMS" : "SMS ALERT"}
          </span>
          <span style={{ fontSize: 12, color: "#94a3b8", fontWeight: 600 }}>Gov-SahakarSetu</span>
        </div>
        <button
          type="button"
          onClick={() => {
            setVisible(false);
            if (onDismiss) onDismiss();
          }}
          style={{
            background: "transparent",
            border: "none",
            color: "#94a3b8",
            fontSize: 18,
            cursor: "pointer",
            padding: 0,
            lineHeight: 1,
          }}
        >
          ✕
        </button>
      </div>

      <div style={{ fontSize: 13, lineHeight: 1.4, color: "#e2e8f0", marginBottom: 12 }}>
        <strong>{isUrgent ? "🚨 [तत्काल इमरजेंसी]" : "📋 [नया काम]"}</strong> {ward || "वार्ड"} में <strong>{trade}</strong> की आवश्यकता है।
        <br />
        <span style={{ color: "#cbd5e1" }}>
          ग्राहक: {customerName} {address ? `· ${address}` : ""}
        </span>
      </div>

      <div style={{ display: "flex", gap: 8 }}>
        {onAccept && (
          <button
            type="button"
            onClick={() => {
              setVisible(false);
              onAccept();
            }}
            style={{
              flex: 1,
              background: "#22c55e",
              color: "#fff",
              border: "none",
              borderRadius: 8,
              padding: "8px 12px",
              fontWeight: 700,
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            काम स्वीकारें (Accept)
          </button>
        )}
        <button
          type="button"
          onClick={() => {
            setVisible(false);
            if (onDismiss) onDismiss();
          }}
          style={{
            background: "rgba(255, 255, 255, 0.1)",
            color: "#e2e8f0",
            border: "none",
            borderRadius: 8,
            padding: "8px 12px",
            fontWeight: 600,
            fontSize: 13,
            cursor: "pointer",
          }}
        >
          बाद में
        </button>
      </div>
    </div>
  );
}
