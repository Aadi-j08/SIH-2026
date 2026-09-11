import { Link, Navigate, Route, Routes, useParams } from "react-router-dom";

import { CalendarIcon, LayoutGrid, Receipt, TrendingUp, Users } from "./components/Icons";
import PortalShell, { BrandMark, PORTALS, PortalTag, UserMenu, Wordmark } from "./components/PortalShell";
import { AuthProvider, RequireAuth } from "./lib/auth";
import Admin from "./pages/Admin";
import Customer from "./pages/Customer";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import PortalLanding from "./pages/PortalLanding";
import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
import Worker from "./pages/Worker";

/** Sabha's desktop sidebar: the dashboard sections, and the signed-in person at the bottom. */
function SabhaSidebar() {
  const p = PORTALS.sabha;
  return (
    <aside className="sidebar">
      <Link to={p.home} className="brand">
        <BrandMark color={p.accent} />
        <Wordmark>
          <small>Cooperative council</small>
        </Wordmark>
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
      <UserMenu portal="sabha" />
    </aside>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />

        {/* Ghar · Home */}
        <Route path="/ghar" element={<PortalLanding portal="ghar" />} />
        <Route path="/ghar/login" element={<SignIn portal="ghar" />} />
        <Route path="/ghar/signup" element={<SignUp portal="ghar" />} />
        <Route
          path="/ghar/home/:bookingId?"
          element={
            <RequireAuth portal="ghar">
              <PortalShell portal="ghar">
                <Customer />
              </PortalShell>
            </RequireAuth>
          }
        />

        {/* Kaam · Work */}
        <Route path="/kaam" element={<PortalLanding portal="kaam" />} />
        <Route path="/kaam/login" element={<SignIn portal="kaam" />} />
        <Route path="/kaam/signup" element={<SignUp portal="kaam" />} />
        <Route
          path="/kaam/home"
          element={
            <RequireAuth portal="kaam">
              <PortalShell portal="kaam">
                <Worker />
              </PortalShell>
            </RequireAuth>
          }
        />

        {/* Sabha · Council */}
        <Route path="/sabha" element={<PortalLanding portal="sabha" />} />
        <Route path="/sabha/login" element={<SignIn portal="sabha" />} />
        <Route path="/sabha/signup" element={<SignUp portal="sabha" />} />
        <Route
          path="/sabha/home"
          element={
            <RequireAuth portal="sabha">
              <PortalShell portal="sabha" sidebar={<SabhaSidebar />}>
                <Admin />
              </PortalShell>
            </RequireAuth>
          }
        />

        {/* the pre-login paths */}
        <Route path="/customer" element={<Navigate to="/ghar/home" replace />} />
        <Route path="/customer/:bookingId" element={<RedirectBooking />} />
        <Route path="/worker" element={<Navigate to="/kaam/home" replace />} />
        <Route path="/admin" element={<Navigate to="/sabha/home" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </AuthProvider>
  );
}

function RedirectBooking() {
  const { bookingId } = useParams();
  return <Navigate to={`/ghar/home/${bookingId}`} replace />;
}
