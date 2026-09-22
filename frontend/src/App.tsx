import { Navigate, Outlet, Route, Routes, useParams } from "react-router-dom";

import PortalShell from "./components/PortalShell";
import SabhaShell from "./components/SabhaShell";
import { AuthProvider, RequireAuth } from "./lib/auth";
import Customer from "./pages/Customer";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import PortalLanding from "./pages/PortalLanding";
import Announcements from "./pages/sabha/Announcements";
import Customers from "./pages/sabha/Customers";
import Demands from "./pages/sabha/Demands";
import Disputes from "./pages/sabha/Disputes";
import Feedback from "./pages/sabha/Feedback";
import Fund from "./pages/sabha/Fund";
import Overview from "./pages/sabha/Overview";
import Payments from "./pages/sabha/Payments";
import Profile from "./pages/sabha/Profile";
import Reports from "./pages/sabha/Reports";
import Settings from "./pages/sabha/Settings";
import SabhaWorkers from "./pages/sabha/Workers";
import SignIn from "./pages/SignIn";
import SignUp from "./pages/SignUp";
import Worker from "./pages/Worker";
import WorkerJobs from "./pages/WorkerJobs";
import WorkerWeek from "./pages/WorkerWeek";

/** Every private Sabha page: signed-in council member, inside the Sabha frame. */
function SabhaArea() {
  return (
    <RequireAuth portal="sabha">
      <SabhaShell>
        <Outlet />
      </SabhaShell>
    </RequireAuth>
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
        <Route
          path="/kaam/week"
          element={
            <RequireAuth portal="kaam">
              <PortalShell portal="kaam">
                <WorkerWeek />
              </PortalShell>
            </RequireAuth>
          }
        />
        <Route
          path="/kaam/jobs"
          element={
            <RequireAuth portal="kaam">
              <PortalShell portal="kaam">
                <WorkerJobs />
              </PortalShell>
            </RequireAuth>
          }
        />

        {/* Sabha · Council */}
        <Route path="/sabha" element={<PortalLanding portal="sabha" />} />
        <Route path="/sabha/login" element={<SignIn portal="sabha" />} />
        <Route path="/sabha/signup" element={<SignUp portal="sabha" />} />
        <Route element={<SabhaArea />}>
          <Route path="/sabha/home" element={<Overview />} />
          <Route path="/sabha/demands" element={<Demands />} />
          <Route path="/sabha/workers" element={<SabhaWorkers />} />
          <Route path="/sabha/customers" element={<Customers />} />
          <Route path="/sabha/payments" element={<Payments />} />
          <Route path="/sabha/fund" element={<Fund />} />
          <Route path="/sabha/disputes" element={<Disputes />} />
          <Route path="/sabha/reports" element={<Reports />} />
          <Route path="/sabha/feedback" element={<Feedback />} />
          <Route path="/sabha/announcements" element={<Announcements />} />
          <Route path="/sabha/profile" element={<Profile />} />
          <Route path="/sabha/settings" element={<Settings />} />
        </Route>

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
