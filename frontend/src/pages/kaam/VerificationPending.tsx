/**
 * Worker onboarding: the page a brand-new Kaam worker lands on after signing up,
 * before the council approves their account. The worker cannot see jobs or
 * appear in the allocation engine until `worker_status` becomes "active".
 */
import { useState } from "react";

import { api, errorMessage } from "../../api";
import { Lock, Refresh, ShieldCheck } from "../../components/Icons";
import { useAuth } from "../../lib/auth";

export default function VerificationPending() {
  const { user, refresh } = useAuth();
  const [polling, setPolling] = useState(false);
  const worker = user?.worker_id ? `worker #${user.worker_id}` : "your worker account";

  const recheck = async () => {
    setPolling(true);
    try {
      await refresh();
    } catch (e) {
      console.error(errorMessage(e));
    } finally {
      setPolling(false);
    }
  };

  const details = [
    { icon: <ShieldCheck size={20} />, label: user?.name ?? "—", hint: "Name" },
    { icon: <Lock size={20} />, label: user?.phone ?? "—", hint: "Phone number" },
    { icon: <Lock size={20} />, label: user?.worker_id ?? "—", hint: "Worker ID" },
  ];

  return (
    <div className="page wide kaam-page">
      <header className="stack" style={{ gap: 6, marginBottom: 24 }}>
        <h1>Account under review</h1>
        <div className="small muted">One moment — the council is verifying your worker profile.</div>
      </header>

      <section className="card" style={{ maxWidth: 420, margin: "0 auto" }}>
        <div className="row" style={{ gap: 16, alignItems: "center", justifyContent: "center" }}>
          <div className="avatar" style={{ width: 56, height: 56 }}>
            {(user?.name ?? worker).slice(0, 2).toUpperCase()}
          </div>
        </div>
        <div className="stack" style={{ gap: 8, marginTop: 12 }}>
          {details.map((d) => (
            <div key={d.hint} className="row between">
              <span className="small muted">{d.hint}</span>
              <span className="small">{d.label}</span>
            </div>
          ))}
        </div>

        <div className="notice" style={{ marginTop: 16 }}>
          You’ll get jobs once the council approves your account. This usually takes a
          few minutes. After approval, the page will refresh automatically.
        </div>

        <div className="row" style={{ gap: 12, marginTop: 16, justifyContent: "center" }}>
          <button type="button" className="btn" onClick={recheck} disabled={polling}>
            {polling ? <Refresh size={16} /> : "Re-check status"}
          </button>
          <button type="button" className="btn outline" onClick={() => void api.auth.logout()}>
            Sign in as someone else
          </button>
        </div>
      </section>
    </div>
  );
}
