import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PlaneIcon, DocIcon, FuelIcon, RouteIcon } from "../components/Icons";
import { login } from "../auth";

function Login() {

  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [slow, setSlow] = useState(false);

  const handleLogin = async () => {

    setError("");

    // empty check
    if (email === "" || password === "") {
      setError("Enter your email and password to continue.");
      return;
    }

    // The credential is checked by the backend — this component never
    // sees the real password, so there is nothing here to read out of
    // the bundle.
    // The backend is on a free tier that sleeps after inactivity, so a
    // first sign-in can take ~30s to wake it. Without a word of warning
    // that is indistinguishable from a broken site, and people give up
    // or hammer the button. Say what is happening once it drags.
    setBusy(true);
    setSlow(false);
    const slowTimer = setTimeout(() => setSlow(true), 4000);

    const result = await login(email, password);

    clearTimeout(slowTimer);
    setBusy(false);
    setSlow(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    navigate("/dashboard");

  };

  const onKeyDown = (event) => {
    if (event.key === "Enter") {
      handleLogin();
    }
  };

  return (

    <div className="login-bg">

      {/* ---------- AMBIENT DECOR ---------- */}

      <span className="ribbon" aria-hidden="true" />
      <span className="aurora a1" aria-hidden="true" />
      <span className="aurora a2" aria-hidden="true" />
      <span className="aurora a3" aria-hidden="true" />
      <span className="aurora a4" aria-hidden="true" />
      <span className="stars far" aria-hidden="true" />
      <span className="stars" aria-hidden="true" />
      <span className="radar" aria-hidden="true" />
      <span className="tracks" aria-hidden="true" />
      <span className="flight f1" aria-hidden="true"><i /></span>
      <span className="flight f3" aria-hidden="true"><i /></span>
      <span className="grain" aria-hidden="true" />

      {/* ---------- LEFT : PITCH ---------- */}

      <section className="login-hero">

        <div className="hero-badge">
          <span className="dot" />
          Flight Operations Suite
        </div>

        <h1>
          ForeFlight navlogs,<br />
          <em>operator-ready</em> in seconds.
        </h1>

        <p>
          Convert ForeFlight HTML exports into fully formatted operational
          flight plans — fuel policy, alternates, enroute winds and ATC plan,
          laid out exactly to your fleet's template.
        </p>

        <div className="hero-points">

          <div className="hero-point">
            <i><DocIcon /></i>
            Print-ready OPS flight plans in ten fleet formats
          </div>

          <div className="hero-point">
            <i><FuelIcon /></i>
            Fuel, contingency and endurance computed per your policy
          </div>

          <div className="hero-point">
            <i><RouteIcon /></i>
            Main route plus two alternates, winds and airport data
          </div>

        </div>

        <div className="hero-formats">
          <span>MLOVE</span>
          <span>DEFAULT</span>
          <span>DEFAULT 1</span>
          <span>VTBBD</span>
          <span>VTVIK</span>
          <span>VTCSP</span>
          <span>INDO PACIFIC 1</span>
          <span>INDO PACIFIC 2</span>
          <span>VTJOE</span>
          <span>VTKCM</span>
        </div>

      </section>

      {/* ---------- RIGHT : SIGN IN ---------- */}

      <section className="login-panel">

        <div className="login-card">

          <div className="plane"><PlaneIcon width={26} height={26} /></div>

          <h2>Sign in</h2>

          <p className="sub">Secure aviation operations portal</p>

          <div className="login-divider" />

          {
            error &&
            <div className="error">{error}</div>
          }

          <div className="login-field">
            <label htmlFor="login-email">Email address</label>
            <input
              id="login-email"
              placeholder="name@eflight.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onKeyDown={onKeyDown}
            />
          </div>

          <div className="login-field">
            <label htmlFor="login-password">Password</label>
            <input
              id="login-password"
              placeholder="••••••••"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              onKeyDown={onKeyDown}
            />
          </div>

          <button onClick={handleLogin} disabled={busy}>
            {busy ? "SIGNING IN…" : "SIGN IN"}
          </button>

          {slow && (
            <p className="waking">
              Waking the server — it sleeps when idle, so the first sign-in
              can take up to a minute. Leave this open.
            </p>
          )}

          <div className="login-foot">
            AUTHORISED PERSONNEL ONLY · EFLIGHT OPS
          </div>

        </div>

      </section>

    </div>

  );

}

export default Login;
