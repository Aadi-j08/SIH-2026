import { Link, Navigate, Route, Routes } from "react-router-dom";

import { ArrowLeft, CalendarIcon, LayoutGrid, Receipt, TrendingUp, Users } from "./components/Icons";
import PortalShell, { BrandMark, PORTALS, PortalTag } from "./components/PortalShell";
import Admin from "./pages/Admin";
import Customer from "./pages/Customer";
import Landing from "./pages/Landing";
import Worker from "./pages/Worker";

/** Sabha's desktop sidebar: the dashboard sections, plus the way back. */
function SabhaSidebar() {
  const p = PORTALS.sabha;
  return (
    <aside className="sidebar">
      <Link to={p.path} className="brand">
        <BrandMark color={p.accent} />
        <span className="wordmark">
          SahakarSetu
          <small>Cooperative council</small>
        </span>
      </Link>
      <PortalTag portal="sabha" />
      <nav aria-label="Dashboard sections">
        <a href="#top" className="active">
          <LayoutGrid size={20} />
          Dashboard
        </a>
        <a href="#bookings">
          <CalendarIcon size={20} />
          Bookings
        </a>
        <a href="#workers">
          <Users size={20} />
          Workers
        </a>
        <a href="#forecast">
          <TrendingUp size={20} />
          Forecast
        </a>
        <a href="#money">
          <Receipt size={20} />
          Ledger
        </a>
      </nav>
      <div className="grow" />
      <Link to="/" className="back">
        <ArrowLeft size={16} />
        All portals
      </Link>
    </aside>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
      <Route
        path="/customer"
        element={
          <PortalShell portal="ghar">
            <Customer />
          </PortalShell>
        }
      />
      <Route
        path="/customer/:bookingId"
        element={
          <PortalShell portal="ghar">
            <Customer />
          </PortalShell>
        }
      />
      <Route
        path="/worker"
        element={
          <PortalShell portal="kaam">
            <Worker />
          </PortalShell>
        }
      />
      <Route
        path="/admin"
        element={
          <PortalShell portal="sabha" sidebar={<SabhaSidebar />}>
            <Admin />
          </PortalShell>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
