// Where the Flask backend lives.
//
// In development this is the local server started with `python server.py`.
// In a deployment the frontend is served from a different origin than the
// backend, so the URL has to come from the build environment instead of
// being baked into the source. Set VITE_API_URL on the host (Vercel,
// Netlify, ...) to the backend's public URL — no trailing slash.
export const API_URL =
  import.meta.env.VITE_API_URL || "http://localhost:5000";
