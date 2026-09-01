// Where the Flask backend lives.
//
// VITE_API_URL wins when the host sets it. Otherwise the fallback is
// chosen by where the page is being served from, NOT by a fixed default:
//
//   served from localhost  -> the local Flask server
//   served from anywhere   -> the deployed backend
//
// A plain "http://localhost:5000" default is wrong the moment a build
// ships without the env var — every visitor's browser then tries to
// reach a server on their own machine, which cannot work and produces a
// confusing "cannot connect" rather than an obvious misconfiguration.
// That is exactly what happened to one of the two Vercel deployments of
// this repo, and it made the site unusable on any device that opened it.
const PRODUCTION_API = "https://eflightops-api.onrender.com";

function isPrivateNetwork(host) {
  if (!host) return false;
  if (host === "localhost" || host === "127.0.0.1" || host === "[::1]") return true;
  if (/^(192\.168\.|10\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)/.test(host)) return true;
  if (host.endsWith(".local") || host.endsWith(".lan") || host.endsWith(".home")) return true;
  return false;
}

function resolveApiUrl() {
  const configured = (import.meta.env.VITE_API_URL || "").trim();
  if (configured) return configured.replace(/\/+$/, "");

  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (isPrivateNetwork(host)) {
      return `http://${host}:5000`;
    }
    return PRODUCTION_API;
  }

  return "http://localhost:5000";
}

export const API_URL = resolveApiUrl();
