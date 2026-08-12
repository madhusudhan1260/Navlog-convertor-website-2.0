import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";

import Login from "./pages/Login";

import Dashboard from "./pages/Dashboard";

import { isSignedIn } from "./auth";

import "./App.css";


// /dashboard used to be reachable by typing the URL, which made the
// login screen decorative. Everything behind the gate goes through here.
function RequireAuth({ children }) {

  if (!isSignedIn()) {
    return <Navigate to="/" replace />;
  }

  return children;

}


// The sign-in screen is not somewhere a signed-in operator ever wants to
// land. Without this, pressing Back off the dashboard - or reopening the
// bare URL - showed a login form to someone who was already through it.
function RedirectIfSignedIn({ children }) {

  if (isSignedIn()) {
    return <Navigate to="/dashboard" replace />;
  }

  return children;

}


function App() {


return (

<BrowserRouter>


<Routes>


<Route
path="/"
element={
  <RedirectIfSignedIn>
    <Login />
  </RedirectIfSignedIn>
}
/>


{/* The chosen format lives in the URL rather than in component state,
    so the browser's Back button steps from the details form back to the
    format picker instead of leaving the dashboard altogether. */}
<Route
path="/dashboard"
element={
  <RequireAuth>
    <Dashboard />
  </RequireAuth>
}
/>


<Route
path="/dashboard/:formatId"
element={
  <RequireAuth>
    <Dashboard />
  </RequireAuth>
}
/>


</Routes>


</BrowserRouter>

)


}


export default App;
