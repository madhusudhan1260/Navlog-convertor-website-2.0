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


function App() {


return (

<BrowserRouter>


<Routes>


<Route
path="/"
element={<Login />}
/>


<Route
path="/dashboard"
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
