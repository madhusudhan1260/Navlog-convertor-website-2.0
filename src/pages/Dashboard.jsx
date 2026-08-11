import { useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import { PlaneIcon, UploadIcon, CheckIcon, DownloadIcon } from "../components/Icons";
import { API_URL } from "../api";
import { authHeader, signOut } from "../auth";

const FORMATS = [
  {
    id: "MLOVE",
    key: "ML",
    note: "A4 · OPS flight plan",
    tips: [
      "Contingency is fixed at 250 lbs / 0:13",
      "Endurance drives the RAMP and T/O FUEL times",
    ],
  },
  {
    id: "DEFAULT",
    key: "DF",
    note: "A4 · standard nav log",
    tips: [
      "Contingency = higher of 5% trip fuel or 30 min hold",
      "Max Trip Fuel is operator-supplied",
    ],
  },
  {
    id: "VTBBD",
    key: "BD",
    note: "Letter · cabin crew, min div",
    tips: [
      "Cabin crew name and count/weight are printed",
      "Contingency = higher of 5% trip or 5 min hold",
    ],
  },
  {
    id: "VTVIK",
    key: "VK",
    note: "A4 · dual ATIS blocks",
    tips: [
      "Contingency is a flat 5% of trip fuel",
      "Min Trip Fuel is operator-supplied",
    ],
  },
  {
    id: "VTCSP",
    key: "CS",
    note: "Letter · plan time & weight",
    tips: [
      "Contingency: 5% of trip fuel, 10% of trip time",
      "Taxi prints a flat 0:10; Min Trip Fuel = REQUIRED fuel",
      "Endurance fills the ENDURANCE and XTRA times — leave it blank and both print empty",
      "First Officer prints as typed; Max Trip Fuel falls back to the tail's own figure",
    ],
  },
  {
    id: "INDOPACIFIC1",
    label: "INDO PACIFIC 1",
    key: "I1",
    note: "A4 · single alternate",
    tips: [
      "Prints the 1 ALT sheet — ALTN1 only, no ALTN2 row",
      "Upload a second alternate and its row is added rather than dropped",
      "Contingency: 5% of trip fuel, 10% of trip time (5 min minimum)",
      "Endurance fills the ENDURANCE and XTRA times",
    ],
  },
  {
    id: "INDOPACIFIC2",
    label: "INDO PACIFIC 2",
    key: "I2",
    note: "A4 · two alternates",
    tips: [
      "Prints the 2 ALT sheet — the ALTN2 row is reserved even before the second alternate is uploaded",
      "Same page-1 layout as INDO PACIFIC 1, shifted down one row from ENDURANCE",
      "Contingency: 5% of trip fuel, 10% of trip time (5 min minimum)",
      "Endurance fills the ENDURANCE and XTRA times",
    ],
  },
  {
    id: "VTJOE",
    key: "JO",
    note: "A4 · ATIS & take-off data page",
    tips: [
      "Adds a hand-fill DEPARTURE ATIS / TAKE OFF DATA / LANDING DATA page",
      "FUEL block carries an MDF row (alternate fuel + final reserve)",
      "Contingency is fixed at 250 lbs / 0:13; taxi time is a flat 0:10",
      "Endurance fills the REQ, EXTRA, T/O FUEL and RAMP times",
    ],
  },
  {
    id: "VTKCM",
    key: "KC",
    note: "A4 · additional & discretionary",
    tips: [
      "Plan block adds an ADDITIONAL row and renames XTRA to DISCRETIONARY",
      "Additional Fuel / Time are operator-entered; Discretionary is what's left of the extra",
      "AIRPORT INFO lists the alternates as ALTN1 / ALTN2 rows",
      "Contingency: 5% of trip fuel, 10% of trip time (5 min minimum)",
    ],
  },
];

// The wire id has no spaces (it is what the backend dispatches on); the
// label is what an operator reads.
const formatLabel = (id) => FORMATS.find((f) => f.id === id)?.label || id;

function Dashboard() {

  const navigate = useNavigate();

  const [files, setFiles] = useState({

    mainFile: null,
    alternate1File: null,
    alternate2File: null

  });

  const [form, setForm] = useState({

    callSign: "",
    pilotName: "",
    coPilotName: "",
    cabinCrewName: "",

    departure: "",
    destination: "",

    flightLevel: "",

    paxWeight: "",
    ccWeight: "",
    maxTripFuel: "",
    contingencyFuel: "",
    contingencyTime: "",
    additionalFuel: "",
    additionalTime: "",

    fuel: "",
    fuelTime: "",
    fuel1: "",
    fuel1Time: "",

    endurance: "",

    icaoFlightPlan: "",

    selectedFormat: "MLOVE"

  });

  const [loading, setLoading] = useState(false);

  const [pdf, setPdf] = useState(null);
  const [pdfName, setPdfName] = useState("flight-plan.pdf");

  const [json, setJson] = useState(null);


  // ================= TEXT INPUT =================

  function update(event) {

    const { name, value } = event.target;

    setForm(previous => ({

      ...previous,

      [name]: value

    }));

  }


  // ================= FILE INPUT =================

  function updateFile(event) {

    const { name, files: selectedFiles } = event.target;

    setFiles(previous => ({

      ...previous,

      [name]: selectedFiles[0]

    }));

  }


  // ================= PROCESS =================

  async function processNavlog() {

    if (!files.mainFile) {

      alert("Please select Main Route HTML File");

      return;

    }

    setLoading(true);

    setPdf(null);

    setJson(null);

    try {

      const formData = new FormData();

      formData.append(
        "mainFile",
        files.mainFile
      );

      if (files.alternate1File) {

        formData.append(
          "alternate1File",
          files.alternate1File
        );

      }

      if (files.alternate2File) {

        formData.append(
          "alternate2File",
          files.alternate2File
        );

      }

      formData.append(

        "userInput",

        JSON.stringify({

          callSign: form.callSign,

          pilotName: form.pilotName,

          coPilotName: form.coPilotName,

          cabinCrewName: form.cabinCrewName,

          departure: form.departure,

          destination: form.destination,

          flightLevel: form.flightLevel,

          paxWeight: form.paxWeight,

          ccWeight: form.ccWeight,

          maxTripFuel: form.maxTripFuel,

          contingencyFuel: form.contingencyFuel,

          contingencyTime: form.contingencyTime,

          additionalFuel: form.additionalFuel,

          additionalTime: form.additionalTime,

          fuel: form.fuel,

          fuelTime: form.fuelTime,

          fuel1: form.fuel1,

          fuel1Time: form.fuel1Time,

          endurance: form.endurance,

          icaoFlightPlan: form.icaoFlightPlan,

          selectedFormat: form.selectedFormat

        })

      );

      const response = await axios.post(

        `${API_URL}/convert`,

        formData,

        {

          headers: {

            "Content-Type": "multipart/form-data",

            ...authHeader()

          }

        }

      );

      // /generated is behind auth too, so the returned URL cannot just be
      // dropped into an <a href> — a plain navigation carries no
      // Authorization header and would come back 401. Fetch it with the
      // token and hand the download an in-memory blob instead.
      const pdfResponse = await fetch(response.data.pdf, {
        headers: authHeader()
      });

      if (!pdfResponse.ok) {
        throw new Error(`Could not retrieve the generated PDF (${pdfResponse.status}).`);
      }

      const blob = await pdfResponse.blob();

      setPdf((previous) => {
        if (previous) URL.revokeObjectURL(previous);
        return URL.createObjectURL(blob);
      });

      setPdfName(response.data.pdf.split("/").pop() || "flight-plan.pdf");

      setJson(response.data.data);

    }

    catch (error) {

      console.error(error);

      alert("Conversion Failed");

    }

    setLoading(false);

  }


  // ================= FILE PICKER =================

  function FilePicker({ name, title, required }) {

    const chosen = files[name];

    return (

      <label className={`file-field ${chosen ? "is-set" : ""}`}>

        <div className="file-row">

          <div className="file-icon">{chosen ? <CheckIcon width={17} height={17} /> : <UploadIcon />}</div>

          <div className="file-text">
            <strong>{title}</strong>
            <span>{chosen ? chosen.name : "Click to select a ForeFlight .html export"}</span>
          </div>

          <div className={`file-badge ${!chosen && required ? "req" : ""}`}>
            {chosen ? "Loaded" : required ? "Required" : "Optional"}
          </div>

        </div>

        <input
          type="file"
          accept=".html,.htm"
          name={name}
          onChange={updateFile}
        />

      </label>

    );

  }

  const crewDone = form.pilotName !== "" || form.callSign !== "";
  const fuelDone = form.endurance !== "" || form.contingencyFuel !== "";
  const fplDone = form.icaoFlightPlan !== "";

  return (

    <div>

      {/* ================= AMBIENT BACKGROUND ================= */}

      <div className="bg-decor" aria-hidden="true">
        <span className="sheet" />
        <span className="orb o1" />
        <span className="orb o2" />
        <span className="orb o3" />
        <span className="orb o4" />
        <span className="orb o5" />
        <span className="tracks" />
      </div>

      {/* ================= HEADER ================= */}

      <header className="header">

        <div className="brand">

          <div className="brand-mark"><PlaneIcon width={20} height={20} /></div>

          <div>
            <h1>EFLIGHT AI</h1>
            <span>Navlog Converter</span>
          </div>

        </div>

        <div className="header-right">

          <div className="header-tag mono">{formatLabel(form.selectedFormat)}</div>

          <div className="header-tag">
            <span className="dot" />
            OPS Generator
          </div>

          <button
            type="button"
            className="header-tag as-button"
            onClick={() => { signOut(); navigate("/", { replace: true }); }}
          >
            Sign out
          </button>

        </div>

      </header>

      <div className="page">

        {/* ================= HERO ================= */}

        <div className="hero">

          <div className="eyebrow">Flight Planning</div>

          <h1>Generate an <em>OPS flight plan</em></h1>

          <p>
            Upload your ForeFlight navlog exports, add the crew and fuel figures
            that ForeFlight doesn't carry, then choose an output format to
            produce a print-ready operational flight plan.
          </p>

          <div className="hero-stats">

            <div className="stat">
              <b>{FORMATS.length}</b>
              <span>Fleet formats</span>
            </div>

            <div className="stat">
              <b>3</b>
              <span>Routes per plan</span>
            </div>

            <div className="stat">
              <b>4</b>
              <span>Pages output</span>
            </div>

            <div className="stat">
              <b>A4<span style={{ opacity: 0.55 }}>/</span>LTR</b>
              <span>Page sizes</span>
            </div>

          </div>

        </div>

        <div className="layout">

          {/* ================= MAIN COLUMN ================= */}

          <main>

            {/* ---- 1. CREW ---- */}

            <section className="section c-indigo">

              <div className="section-head">
                <div className="section-num">01</div>
                <h2>Crew &amp; Aircraft</h2>
              </div>

              <div className="section-body">

                <div className="grid3">

                  <div className="field">
                    <label>Call Sign</label>
                    <input name="callSign" placeholder="VTECG" value={form.callSign} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Pilot in Command</label>
                    <input name="pilotName" placeholder="CAPT SHREYAS VYAS" value={form.pilotName} onChange={update} />
                  </div>

                  <div className="field">
                    <label>First Officer</label>
                    <input name="coPilotName" placeholder="CAPT SANSKAR MISHRA" value={form.coPilotName} onChange={update} />
                  </div>

                </div>

                <div className="grid2">

                  <div className="field">
                    <label>Cabin Crew Name <span className="opt">VTBBD</span></label>
                    <input name="cabinCrewName" placeholder="MS SHWETA DIWAN" value={form.cabinCrewName} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Cabin Crew Count <span className="opt">VTBBD</span></label>
                    <input name="ccWeight" placeholder="1  →  prints 1 - 187" value={form.ccWeight} onChange={update} />
                  </div>

                </div>

              </div>

            </section>

            {/* ---- 2. ROUTE ---- */}

            <section className="section c-cyan">

              <div className="section-head">
                <div className="section-num">02</div>
                <h2>Route</h2>
                <span className="hint">Blank = use values parsed from the HTML</span>
              </div>

              <div className="section-body">

                <div className="grid3">

                  <div className="field">
                    <label>Departure ICAO</label>
                    <input name="departure" placeholder="VIDP" value={form.departure} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Destination ICAO</label>
                    <input name="destination" placeholder="VECC" value={form.destination} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Flight Level</label>
                    <input name="flightLevel" placeholder="FL450" value={form.flightLevel} onChange={update} />
                  </div>

                </div>

              </div>

            </section>

            {/* ---- 3. FUEL & WEIGHTS ---- */}

            <section className="section c-amber">

              <div className="section-head">
                <div className="section-num">03</div>
                <h2>Fuel &amp; Weights</h2>
                <span className="hint">Not carried by ForeFlight — enter per flight</span>
              </div>

              <div className="section-body">

                <div className="grid3">

                  <div className="field">
                    <label>PAX</label>
                    <input name="paxWeight" placeholder="1  →  prints 1 - 165 on VTBBD" value={form.paxWeight} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Max Trip Fuel</label>
                    <input name="maxTripFuel" placeholder="3329" value={form.maxTripFuel} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Endurance</label>
                    <input name="endurance" placeholder="4:15" value={form.endurance} onChange={update} />
                  </div>

                </div>

                <div className="grid2">

                  <div className="field">
                    <label>Contingency Fuel (lbs)</label>
                    <input name="contingencyFuel" placeholder="250" value={form.contingencyFuel} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Contingency Time</label>
                    <input name="contingencyTime" placeholder="0:13" value={form.contingencyTime} onChange={update} />
                  </div>

                </div>

                <div className="grid2">

                  <div className="field">
                    <label>Additional Fuel (lbs) <span className="opt">VTKCM</span></label>
                    <input name="additionalFuel" placeholder="100" value={form.additionalFuel} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Additional Time <span className="opt">VTKCM</span></label>
                    <input name="additionalTime" placeholder="0:10" value={form.additionalTime} onChange={update} />
                  </div>

                </div>

                <div className="grid2">

                  <div className="field">
                    <label>Fuel <span className="opt">+ TRIP</span></label>
                    <input name="fuel" placeholder="lbs added to TRIP" value={form.fuel} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Fuel 1 <span className="opt">+ ALT1</span></label>
                    <input name="fuel1" placeholder="lbs added to ALT1" value={form.fuel1} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Fuel Time <span className="opt">+ TAXI</span></label>
                    <input name="fuelTime" placeholder="0:10" value={form.fuelTime} onChange={update} />
                  </div>

                  <div className="field">
                    <label>Fuel 1 Time <span className="opt">+ ALT1</span></label>
                    <input name="fuel1Time" placeholder="0:05" value={form.fuel1Time} onChange={update} />
                  </div>

                </div>

              </div>

            </section>

            {/* ---- 4. FILES ---- */}

            <section className="section c-violet">

              <div className="section-head">
                <div className="section-num">04</div>
                <h2>ForeFlight HTML Exports</h2>
              </div>

              <div className="section-body">

                <div className="grid1">

                  <FilePicker name="mainFile" title="Main Route" required />
                  <FilePicker name="alternate1File" title="Alternate 1" />
                  <FilePicker name="alternate2File" title="Alternate 2" />

                </div>

              </div>

            </section>

            {/* ---- 5. ATC FLIGHT PLAN ---- */}

            <section className="section c-teal">

              <div className="section-head">
                <div className="section-num">05</div>
                <h2>ATC Flight Plan</h2>
                <span className="hint">Printed verbatim on the final page</span>
              </div>

              <div className="section-body">

                <div className="field">
                  <label>Full ICAO FPL text</label>
                  <textarea
                    name="icaoFlightPlan"
                    placeholder={"(FPL-VTECG-IN\n-C25A/L-SDFGHRWY/LB1\n-VIDP0945\n-N0411F450 DPN V18 ALI G452 LKN R460 CEA\n..."}
                    value={form.icaoFlightPlan}
                    onChange={update}
                    rows={8}
                  />
                </div>

              </div>

            </section>

            {/* ---- JSON ---- */}

            {
              json && (

                <details className="json-block">

                  <summary>Parsed flight data (JSON)</summary>

                  <pre className="json-box">
                    {JSON.stringify(json, null, 2)}
                  </pre>

                </details>

              )
            }

          </main>

          {/* ================= SIDEBAR ================= */}

          <aside className="aside">

            {/* format */}

            <div className="panel">

              <div className="panel-head">Output Format</div>

              <div className="panel-body">

                <div className="format-list">

                  {
                    FORMATS.map(item => (

                      <button
                        key={item.id}
                        type="button"
                        className={`format-option ${form.selectedFormat === item.id ? "active" : ""}`}
                        onClick={() => setForm(prev => ({ ...prev, selectedFormat: item.id }))}
                      >
                        <span className="format-key">{item.key}</span>

                        <span className="format-text">
                          <strong>{item.label || item.id}</strong>
                          <span>{item.note}</span>
                        </span>
                      </button>

                    ))
                  }

                </div>

              </div>

            </div>

            {/* generate */}

            <div className="panel">

              <div className="panel-head">Generate</div>

              <div className="panel-body">

                <div className="checklist">

                  <div className={`check-row ${files.mainFile ? "done" : ""}`}>
                    <i>{files.mainFile ? "✓" : "1"}</i>
                    Main route HTML
                  </div>

                  <div className={`check-row ${crewDone ? "done" : ""}`}>
                    <i>{crewDone ? "✓" : "2"}</i>
                    Crew details
                  </div>

                  <div className={`check-row ${fuelDone ? "done" : ""}`}>
                    <i>{fuelDone ? "✓" : "3"}</i>
                    Fuel figures
                  </div>

                  <div className={`check-row ${fplDone ? "done" : ""}`}>
                    <i>{fplDone ? "✓" : "4"}</i>
                    ATC flight plan
                  </div>

                </div>

                <div style={{ height: 16 }} />

                <button
                  className="process"
                  onClick={processNavlog}
                  disabled={loading}
                >
                  {
                    loading
                      ? <>
                          <span className="spinner" />
                          Generating…
                        </>
                      : <>Generate OPS PDF</>
                  }
                </button>

                <div className="action-note">
                  {
                    files.mainFile
                      ? `Ready — ${formatLabel(form.selectedFormat)} format`
                      : "Main route HTML required"
                  }
                </div>

              </div>

            </div>

            {/* format notes */}

            <div className="panel">

              <div className="panel-head">
                {formatLabel(form.selectedFormat)} Notes
              </div>

              <div className="panel-body">

                <ul className="notes">
                  {
                    (FORMATS.find(f => f.id === form.selectedFormat)?.tips || [])
                      .map(tip => <li key={tip}>{tip}</li>)
                  }
                  <li>Blank operational fields print as hand-fill lines.</li>
                </ul>

              </div>

            </div>

            {/* result */}

            {
              pdf && (

                <div className="result">

                  <div className="result-top">

                    <div className="ok-icon"><CheckIcon width={17} height={17} /></div>

                    <div>
                      <strong>Plan generated</strong>
                      <p>{formatLabel(form.selectedFormat)} · ready to print</p>
                    </div>

                  </div>

                  <a
                    href={pdf}
                    download={pdfName}
                    target="_blank"
                    rel="noreferrer"
                    className="download-btn"
                  >
                    <DownloadIcon width={16} height={16} />
                    Download PDF
                  </a>

                </div>

              )
            }

          </aside>

        </div>

      </div>

    </div>

  );

}

export default Dashboard;
