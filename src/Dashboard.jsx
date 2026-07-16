import { useState } from "react";
import axios from "axios";

const initialLinks = {
  mainUrl: "",
  alternate1Url: "",
  alternate2Url: ""
};

const initialUserInput = {
  callSign: "",
  pilotName: "",
  coPilotName: "",
  departure: "",
  destination: "",
  pax: "",
  paxWeight: "",
  maxTripFuel: "",
  endurance: "",
  flightLevel: "",
  shortFPL: "",
  selectedFormat:
    "Forum Aviation Format"
};

const manualFields = [
  ["callSign", "CALL SIGN"],
  ["pilotName", "PILOT NAME (PIC)"],
  ["coPilotName", "CO PILOT NAME (F/O)"],
  ["departure", "DEPARTURE AIRPORT"],
  ["destination", "DESTINATION AIRPORT"],
  ["pax", "PAX COUNT"],
  ["paxWeight", "PAX WEIGHT"],
  ["maxTripFuel", "MAX TRIP FUEL"],
  ["endurance", "ENDURANCE TIME"],
  ["flightLevel", "FLIGHT LEVEL"]
];

function Dashboard() {
  const [links, setLinks] =
    useState(initialLinks);

  const [userInput, setUserInput] =
    useState(initialUserInput);

  const [data, setData] =
    useState(null);

  const [pdf, setPdf] =
    useState("");

  const [loading, setLoading] =
    useState(false);

  const [error, setError] =
    useState("");

  function updateLink(event) {
    const { name, value } = event.target;

    setLinks((previous) => ({
      ...previous,
      [name]: value
    }));
  }

  function updateInput(event) {
    const { name, value } = event.target;

    setUserInput((previous) => ({
      ...previous,
      [name]: value
    }));
  }

  async function processNavlog(event) {
    event.preventDefault();

    setLoading(true);
    setError("");
    setPdf("");
    setData(null);

    try {
      const response = await axios.post(
        "http://localhost:5000/convert",
        {
          links,
          userInput
        }
      );

      setData(response.data.data);
      setPdf(response.data.pdf);
    } catch (requestError) {
      setError(
        requestError.response?.data?.message ||
          "Navlog conversion failed."
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main>
      <header className="header">
        <h1>EFLIGHT AI</h1>

        <span>NAVLOG CONVERTER</span>

        <span>OPS FPL</span>
      </header>

      <form
        className="form-card"
        onSubmit={processNavlog}
      >
        <h2>
          Generate Operational Flight Plan
        </h2>

        <fieldset>
          <legend>ROUTE LINKS</legend>

          <label>
            MAIN FOREFLIGHT HTML URL

            <input
              required
              type="url"
              name="mainUrl"
              value={links.mainUrl}
              onChange={updateLink}
            />
          </label>

          <label>
            FIRST ALTERNATE FOREFLIGHT HTML URL

            <input
              type="url"
              name="alternate1Url"
              value={links.alternate1Url}
              onChange={updateLink}
            />
          </label>

          <label>
            SECOND ALTERNATE FOREFLIGHT HTML URL

            <input
              type="url"
              name="alternate2Url"
              value={links.alternate2Url}
              onChange={updateLink}
            />
          </label>
        </fieldset>

        <fieldset className="grid">
          <legend>MANUAL DATA</legend>

          {manualFields.map(
            ([name, label]) => (
              <label key={name}>
                {label}

                <input
                  name={name}
                  value={userInput[name]}
                  onChange={updateInput}
                />
              </label>
            )
          )}

          <label className="wide">
            SHORT FPL

            <textarea
              name="shortFPL"
              value={userInput.shortFPL}
              onChange={updateInput}
              rows="4"
            />
          </label>

          <label>
            FORMAT

            <select
              name="selectedFormat"
              value={
                userInput.selectedFormat
              }
              onChange={updateInput}
            >
              <option>
                Forum Aviation Format
              </option>

              <option>
                Custom Format
              </option>
            </select>
          </label>
        </fieldset>

        <button
          className="process"
          disabled={loading}
        >
          {loading
            ? "AI CREATING OPS FPL..."
            : "PROCESS"}
        </button>

        {error && (
          <p
            className="error"
            role="alert"
          >
            {error}
          </p>
        )}

        {pdf && (
          <a
            className="download-btn"
            href={pdf}
            target="_blank"
            rel="noreferrer"
          >
            DOWNLOAD PDF
          </a>
        )}

        {data && (
          <details>
            <summary>
              VIEW GENERATED JSON
            </summary>

            <pre>
              {JSON.stringify(
                data,
                null,
                2
              )}
            </pre>
          </details>
        )}
      </form>
    </main>
  );
}

export default Dashboard;