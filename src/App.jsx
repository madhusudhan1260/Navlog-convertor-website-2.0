import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Dashboard from "./pages/Dashboard";

import "./App.css";


function App() {

  return (

    <BrowserRouter>

      <Routes>

        <Route path="/" element={<Navigate to="/dashboard" replace />} />

        {/* The chosen format lives in the URL rather than in component
            state, so the browser's Back button steps from the details
            form back to the format picker instead of leaving the
            dashboard altogether. */}
        <Route path="/dashboard" element={<Dashboard />} />

        <Route path="/dashboard/:formatId" element={<Dashboard />} />

      </Routes>

    </BrowserRouter>

  );

}

export default App;
