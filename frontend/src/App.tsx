import { Link, Route, Routes } from "react-router-dom";
import ClientWorkspace from "./pages/ClientWorkspace";
import DesignerPortal from "./pages/DesignerPortal";
import AdminPortal from "./pages/AdminPortal";

export default function App() {
  return (
    <div className="min-h-screen">
      <nav className="fixed top-0 left-0 right-0 z-50 flex gap-4 p-3 text-sm bg-black/40 backdrop-blur">
        <Link to="/client">Client</Link>
        <Link to="/designer">Designer</Link>
        <Link to="/admin">Admin</Link>
      </nav>
      <Routes>
        <Route path="/" element={<ClientWorkspace />} />
        <Route path="/client" element={<ClientWorkspace />} />
        <Route path="/designer" element={<DesignerPortal />} />
        <Route path="/admin" element={<AdminPortal />} />
      </Routes>
    </div>
  );
}
