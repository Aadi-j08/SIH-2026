/** Announcements: not wired to the backend yet — says so, rather than pretending. */
import { Megaphone } from "../../components/Icons";

export default function Announcements() {
  return (
    <div className="page wide sabha-page">
      <div className="stack" style={{ gap: 4 }}>
        <h1 style={{ fontSize: 28 }}>Announcements</h1>
        <div className="sub">Notices from the council to every member — meeting dates, new services, welfare payouts</div>
      </div>
      <div className="panel" style={{ alignItems: "center", textAlign: "center", padding: 40 }}>
        <Megaphone size={32} style={{ color: "var(--indigo)" }} />
        <div className="display" style={{ fontSize: 18, fontWeight: 700 }}>Coming next</div>
        <div className="small muted" style={{ maxWidth: 420 }}>
          Announcements will be posted here and shown to workers in Kaam and households in Ghar. The council posts; members read. Not connected yet.
        </div>
      </div>
    </div>
  );
}
