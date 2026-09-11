import { NavLink, Navigate, Route, Routes } from "react-router-dom";

import Admin from "./pages/Admin";
import Customer from "./pages/Customer";
import Worker from "./pages/Worker";

export default function App() {
  return (
    <div className="shell">
      <header className="topbar">
        <NavLink to="/" className="wordmark">
          SahakarSetu
          <small>Neighbourhood workers' cooperative</small>
        </NavLink>
        <nav className="roles" aria-label="Switch role">
          <NavLink to="/customer">Customer</NavLink>
          <NavLink to="/worker">Worker</NavLink>
          <NavLink to="/admin">Admin</NavLink>
        </nav>
      </header>
      <Routes>
        <Route path="/" element={<Navigate to="/customer" replace />} />
        <Route path="/customer" element={<Customer />} />
        <Route path="/customer/:bookingId" element={<Customer />} />
        <Route path="/worker" element={<Worker />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="*" element={<Navigate to="/customer" replace />} />
      </Routes>
    </div>
  );
}
