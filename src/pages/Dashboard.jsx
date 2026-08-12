import { useState, useEffect } from "react";
import { useNavigate, useParams, Navigate } from "react-router-dom";
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
      "Contingency: 5% of trip fuel, 10% of trip time (5 min minimum)",
      "Taxi prints a flat 0:10; Min Trip Fuel = REQUIRED fuel",
      "A second alternate adds an ALTN2 row and moves the block below it down",
    ],
  },
  {
    id: "DEFAULT1",
    label: "DEFAULT 1",
    key: "D1",
    note: "A4 · flat navlog, 3 pages",
    tips: [
      "Contingency: 5% of trip fuel, 10% of trip time (5 min minimum)",
      "Taxi prints a flat 0:10; Min Trip Fuel = REQUIRED fuel",
      "Waypoints with a navaid print the ident and city together, frequency beneath",
      "TRACK prints the average wind's direction, as the operator's sheet does",
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

// Some fleets file more than one sheet under the same name, so the picker
// shows one card per family and opens it to reveal the variants rather than
// putting near-identical cards side by side.
const FAMILY_META = {
  DEFAULT: {
    key: "DF",
    note: "A4 · 2 sheets",
    members: ["DEFAULT", "DEFAULT1"],
    tips: [
      "Both print the same operator sheet",
      "Flat navlog, sized to its own contents",
      "A second alternate adds the ALTN2 row",
    ],
  },
  "INDO PACIFIC": {
    key: "IP",
    note: "A4 · 2 sheets",
    members: ["INDOPACIFIC1", "INDOPACIFIC2"],
    tips: [
      "INDO PACIFIC 1 — single alternate, no ALTN2 row",
      "INDO PACIFIC 2 — reserves the ALTN2 row",
      "Same page-1 layout; the 2 ALT sheet sits one row lower",
    ],
  },
};

// One entry per card on the picker, in the order the formats are declared.
// A family takes the position of its first member.
const FAMILIES = (() => {
  const belongsTo = {};
  for (const [name, meta] of Object.entries(FAMILY_META)) {
    for (const id of meta.members) belongsTo[id] = name;
  }

  const cards = [];
  const seen = new Set();

  for (const format of FORMATS) {
    const family = belongsTo[format.id];

    if (!family) {
      cards.push({
        name: format.label || format.id,
        key: format.key,
        note: format.note,
        tips: format.tips || [],
        members: [format],
      });
      continue;
    }

    if (seen.has(family)) continue;
    seen.add(family);

    const meta = FAMILY_META[family];
    cards.push({
      name: family,
      key: meta.key,
      note: meta.note,
      tips: meta.tips,
      members: meta.members.map((id) => FORMATS.find((f) => f.id === id)),
    });
  }

  return cards;
})();

const ALL_FORMATS = FORMATS.map((f) => f.id);

const except = (...ids) => ALL_FORMATS.filter((id) => !ids.includes(id));

// Which formats each operator-entered field actually changes.
//
// Measured, not assumed: every format was rendered twice - once with the
// field blank and once with it set - and the two PDFs compared. A format is
// listed here only where the field demonstrably changes its sheet, so the
// form for a given format never shows a box that would do nothing.
//
const FIELD_USAGE = {
  callSign: ["MLOVE", "VTBBD", "VTJOE"],
  pilotName: ALL_FORMATS,
  coPilotName: ALL_FORMATS,
  cabinCrewName: ["VTBBD"],
  ccWeight: ["VTBBD"],

  departure: ALL_FORMATS,
  destination: ALL_FORMATS,
  flightLevel: ALL_FORMATS,

  paxWeight: ALL_FORMATS,
  maxTripFuel: ["DEFAULT", "DEFAULT1", "VTVIK", "VTCSP", "INDOPACIFIC1",
                "INDOPACIFIC2", "VTKCM"],
  endurance: ALL_FORMATS,
  contingencyFuel: ALL_FORMATS,
  contingencyTime: ALL_FORMATS,
  additionalFuel: ["VTKCM"],
  additionalTime: ["VTKCM"],
  fuel: ALL_FORMATS,
  fuel1: ALL_FORMATS,
  fuelTime: except("VTVIK"),
  fuel1Time: ALL_FORMATS,

  icaoFlightPlan: ALL_FORMATS,
};

// The detail form as data, so a format's sheet can be assembled by filtering
// rather than by threading a condition through every input.
const FORM_SECTIONS = [
  {
    num: "01",
    title: "Crew & Aircraft",
    accent: "c-indigo",
    rows: [
      {
        cols: 3,
        fields: [
          { name: "callSign", label: "Call Sign", placeholder: "VTECG" },
          { name: "pilotName", label: "Pilot in Command", placeholder: "CAPT SHREYAS VYAS" },
          { name: "coPilotName", label: "First Officer", placeholder: "CAPT SANSKAR MISHRA" },
        ],
      },
      {
        cols: 2,
        fields: [
          { name: "cabinCrewName", label: "Cabin Crew Name", placeholder: "MS SHWETA DIWAN" },
          { name: "ccWeight", label: "Cabin Crew Count", placeholder: "1  →  prints 1 - 187" },
        ],
      },
    ],
  },
  {
    num: "02",
    title: "Route",
    accent: "c-cyan",
    hint: "Blank = use values parsed from the HTML",
    rows: [
      {
        cols: 3,
        fields: [
          { name: "departure", label: "Departure ICAO", placeholder: "VIDP" },
          { name: "destination", label: "Destination ICAO", placeholder: "VECC" },
          { name: "flightLevel", label: "Flight Level", placeholder: "FL450" },
        ],
      },
    ],
  },
  {
    num: "03",
    title: "Fuel & Weights",
    accent: "c-amber",
    hint: "Not carried by ForeFlight — enter per flight",
    rows: [
      {
        cols: 3,
        fields: [
          { name: "paxWeight", label: "PAX", placeholder: "1  →  prints 1 - 165 on VTBBD" },
          { name: "maxTripFuel", label: "Max Trip Fuel", placeholder: "3329" },
          { name: "endurance", label: "Endurance", placeholder: "4:15" },
        ],
      },
      {
        cols: 2,
        fields: [
          { name: "contingencyFuel", label: "Contingency Fuel (lbs)", placeholder: "250" },
          { name: "contingencyTime", label: "Contingency Time", placeholder: "0:13" },
        ],
      },
      {
        cols: 2,
        fields: [
          { name: "additionalFuel", label: "Additional Fuel (lbs)", placeholder: "100" },
          { name: "additionalTime", label: "Additional Time", placeholder: "0:10" },
        ],
      },
      {
        cols: 2,
        fields: [
          { name: "fuel", label: "Fuel", badge: "+ TRIP", placeholder: "lbs added to TRIP" },
          { name: "fuel1", label: "Fuel 1", badge: "+ ALT1", placeholder: "lbs added to ALT1" },
          { name: "fuelTime", label: "Fuel Time", badge: "+ TAXI", placeholder: "0:10" },
          { name: "fuel1Time", label: "Fuel 1 Time", badge: "+ ALT1", placeholder: "0:05" },
        ],
      },
    ],
  },
];

// What the backend is doing while the operator waits. These are the real
// stages of /convert — parse, transform, render — so the strip advancing
// is an honest account of the work, not a fake progress bar. It is time-
// driven rather than event-driven because the request is a single POST
// with no intermediate reporting; the last stage therefore holds until
// the response lands rather than claiming completion.
const STAGES = [
  "Reading ForeFlight export",
  "Parsing waypoints and winds",
  "Computing fuel and times",
  "Rendering the OPS PDF",
];

const STAGE_MS = 900;

// Counts a hero figure up from zero on mount. Reduced-motion users get
// the final number immediately — an animated count is exactly the kind
// of movement that setting asks us to drop.
function CountUp({ to, duration = 1050 }) {

  const [value, setValue] = useState(0);

  useEffect(() => {

    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    // requestAnimationFrame does not fire in a hidden tab, so a page loaded
    // in the background would sit on 0 — a wrong figure on screen — until
    // it was looked at. Nobody is watching an animation they cannot see, so
    // a hidden tab gets the real number straight away.
    if (still || document.hidden) {
      setValue(to);
      return;
    }

    let frame;
    const started = performance.now();

    const step = (now) => {
      const t = Math.min(1, (now - started) / duration);
      // ease-out cubic: quick off the mark, settles onto the figure
      setValue(Math.round(to * (1 - Math.pow(1 - t, 3))));
      if (t < 1) frame = requestAnimationFrame(step);
    };

    frame = requestAnimationFrame(step);

    return () => cancelAnimationFrame(frame);

  }, [to, duration]);

  return <>{value}</>;

}

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

  // The dashboard is a two-step flow: pick the output format, then fill in
  // the details that format actually prints. Which step you are on is the
  // URL, not component state - /dashboard is the picker and
  // /dashboard/<FORMAT> is the form - so the browser's Back button steps
  // back to the picker rather than off the dashboard entirely.
  const { formatId } = useParams();

  const knownFormat = FORMATS.some((f) => f.id === formatId);
  const step = formatId && knownFormat ? "details" : "format";

  // Which family card is expanded on the picker (the ones with variants).
  const [openFamily, setOpenFamily] = useState(null);

  // The URL is the source of truth for the format; mirror it into the form
  // so the value posted to /convert always matches the page you are on.
  useEffect(() => {
    if (formatId && FORMATS.some((f) => f.id === formatId)) {
      setForm((previous) =>
        previous.selectedFormat === formatId
          ? previous
          : { ...previous, selectedFormat: formatId }
      );
    }
  }, [formatId]);

  // Which line of the flight strip is lit while a conversion runs.
  const [stage, setStage] = useState(0);

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

    setStage(0);

    setPdf(null);

    setJson(null);

    // Walks the strip forward and stops on the last stage, which then
    // holds until the response arrives — so the display never reads
    // "finished" while the request is still open.
    const ticker = setInterval(
      () => setStage((current) => Math.min(current + 1, STAGES.length - 1)),
      STAGE_MS
    );

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

      // A blanket "Conversion Failed" hides the one thing worth knowing.
      // The backend already answers a failed /convert with
      // {success: false, message: "<the actual exception>"}, so surface
      // that; a session that has quietly expired gets its own wording
      // because the fix is to sign in again, not to change the navlog.
      const status = error?.response?.status;
      const backendMessage = error?.response?.data?.message;

      let detail;

      if (status === 401) {
        detail = "Your session has expired. Sign in again and retry.";
      }
      else if (backendMessage) {
        detail = backendMessage;
      }
      else if (error?.message === "Network Error") {
        detail =
          `Could not reach the backend at ${API_URL}. ` +
          "Check that the Flask server is running.";
      }
      else {
        detail = error?.message || "Unknown error.";
      }

      alert(`Conversion Failed\n\n${detail}`);

    }

    clearInterval(ticker);

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

  // ================= FORMAT-AWARE FORM =================

  const uses = (name) =>
    (FIELD_USAGE[name] || ALL_FORMATS).includes(form.selectedFormat);

  // Keep only the fields this format prints, drop rows that empty out, then
  // drop sections that have no rows left.
  const visibleSections = FORM_SECTIONS.map((section) => ({
    ...section,
    rows: section.rows
      .map((row) => ({ ...row, fields: row.fields.filter((f) => uses(f.name)) }))
      .filter((row) => row.fields.length > 0),
  })).filter((section) => section.rows.length > 0);

  const hiddenCount =
    FORM_SECTIONS.reduce(
      (total, s) => total + s.rows.reduce((n, r) => n + r.fields.length, 0), 0
    ) -
    visibleSections.reduce(
      (total, s) => total + s.rows.reduce((n, r) => n + r.fields.length, 0), 0
    );

  const chosen = FORMATS.find((f) => f.id === form.selectedFormat);

  function pickFormat(id) {
    navigate(`/dashboard/${id}`);
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function backToPicker() {
    navigate("/dashboard");
    window.scrollTo({ top: 0, behavior: "auto" });
  }

  function renderField(field) {
    return (
      <div className="field" key={field.name}>
        <label>
          {field.label}
          {field.badge ? <span className="opt">{field.badge}</span> : null}
        </label>
        <input
          name={field.name}
          placeholder={field.placeholder}
          value={form[field.name]}
          onChange={update}
        />
      </div>
    );
  }

  // A typed or stale /dashboard/<id> that names no known format falls back
  // to the picker instead of rendering a form for nothing.
  if (formatId && !knownFormat) {
    return <Navigate to="/dashboard" replace />;
  }

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
        <span className="radar" />
        <span className="compass" />
        <span className="navaid n1" />
        <span className="navaid n2" />
        <span className="navaid n3" />
        <span className="flight f3"><i /></span>
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

          {/* keyed on the format so React remounts the span and the
              departure-board flip replays on every change */}
          <div className="header-tag mono">
            <span className="flap" key={form.selectedFormat}>
              {formatLabel(form.selectedFormat)}
            </span>
          </div>

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

          <span className="flight f1" aria-hidden="true"><i /></span>
          <span className="flight f2" aria-hidden="true"><i /></span>
          <span className="flight f4" aria-hidden="true"><i /></span>
          <span className="runway" aria-hidden="true" />

          <div className="eyebrow">
            {step === "format" ? "Step 1 of 2" : "Step 2 of 2"}
          </div>

          {
            step === "format"
              ? <h1>Choose an <em>output format</em></h1>
              : <h1>Fill in the <em>{formatLabel(form.selectedFormat)}</em> details</h1>
          }

          <p>
            {
              step === "format"
                ? "Every fleet prints its operational flight plan to its own template. "
                  + "Pick one and the next step asks only for the figures that template "
                  + "actually prints."
                : "Upload your ForeFlight navlog exports and add the figures ForeFlight "
                  + "doesn't carry. Anything left blank prints as a hand-fill line."
            }
          </p>

          <div className="hero-stats">

            <div className="stat">
              <b><CountUp to={FORMATS.length} /></b>
              <span>Fleet formats</span>
            </div>

            <div className="stat">
              <b><CountUp to={3} /></b>
              <span>Routes per plan</span>
            </div>

            <div className="stat">
              <b><CountUp to={4} /></b>
              <span>Pages output</span>
            </div>

            <div className="stat">
              <b>A4<span style={{ opacity: 0.55 }}>/</span>LTR</b>
              <span>Page sizes</span>
            </div>

          </div>

        </div>

        {/* ================= STEP 1: FORMAT PICKER ================= */}

        {
          step === "format" && (

            <div className="picker">

              {
                FAMILIES.map((card, index) => {

                  const single = card.members.length === 1;
                  const isOpen = openFamily === card.name;
                  const holdsCurrent = card.members
                    .some(m => m.id === form.selectedFormat);

                  return (

                    <div
                      key={card.name}
                      className={
                        "picker-card"
                        + (holdsCurrent ? " is-current" : "")
                        + (isOpen ? " is-open" : "")
                      }
                      style={{ animationDelay: `${0.04 * index}s` }}
                    >

                      <button
                        type="button"
                        className="picker-head"
                        onClick={() =>
                          single
                            ? pickFormat(card.members[0].id)
                            : setOpenFamily(isOpen ? null : card.name)
                        }
                        aria-expanded={single ? undefined : isOpen}
                      >

                        <div className="picker-top">
                          <span className="picker-key">{card.key}</span>
                          <span className="picker-name">
                            <strong>{card.name}</strong>
                            <span>{card.note}</span>
                          </span>
                        </div>

                        <ul className="picker-tips">
                          {card.tips.slice(0, 3).map(tip => (
                            <li key={tip}>{tip}</li>
                          ))}
                        </ul>

                        <span className="picker-go">
                          {single
                            ? "Fill in details"
                            : isOpen
                              ? "Hide sheets"
                              : `Choose one of ${card.members.length} sheets`}
                          <i aria-hidden="true">{single ? "\u2192" : "\u25be"}</i>
                        </span>

                      </button>

                      {
                        !single && isOpen && (

                          <div className="picker-variants">
                            {
                              card.members.map(member => (

                                <button
                                  type="button"
                                  key={member.id}
                                  className={
                                    "variant"
                                    + (form.selectedFormat === member.id ? " is-current" : "")
                                  }
                                  onClick={() => pickFormat(member.id)}
                                >
                                  <span className="variant-key">{member.key}</span>
                                  <span className="variant-text">
                                    <strong>{member.label || member.id}</strong>
                                    <span>{member.note}</span>
                                  </span>
                                  <i aria-hidden="true">&rarr;</i>
                                </button>

                              ))
                            }
                          </div>

                        )
                      }

                    </div>

                  );

                })
              }

            </div>

          )
        }

        {/* ================= STEP 2: DETAILS ================= */}

        {
          step === "details" && (

        <div className="layout">

          {/* ================= MAIN COLUMN ================= */}

          <main>

            {/* ---- FORMAT-SPECIFIC FIELDS ---- */}

            {
              visibleSections.map(section => (

                <section className={`section ${section.accent}`} key={section.num}>

                  <div className="section-head">
                    <div className="section-num">{section.num}</div>
                    <h2>{section.title}</h2>
                    {section.hint ? <span className="hint">{section.hint}</span> : null}
                  </div>

                  <div className="section-body">
                    {
                      section.rows.map((row, index) => (
                        <div
                          className={`grid${Math.min(row.cols, row.fields.length)}`}
                          key={index}
                        >
                          {row.fields.map(renderField)}
                        </div>
                      ))
                    }
                  </div>

                </section>

              ))
            }


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

            {/* the format chosen in step 1 */}

            <div className="panel">

              <div className="panel-head">Output Format</div>

              <div className="panel-body">

                <div className="chosen">

                  <span className="format-key">{chosen?.key}</span>

                  <span className="format-text">
                    <strong>{formatLabel(form.selectedFormat)}</strong>
                    <span>{chosen?.note}</span>
                  </span>

                </div>

                <button
                  type="button"
                  className="change-format"
                  onClick={backToPicker}
                >
                  Change format
                </button>

                {
                  hiddenCount > 0 && (
                    <div className="action-note">
                      {hiddenCount} field{hiddenCount === 1 ? "" : "s"} hidden —
                      {" "}{formatLabel(form.selectedFormat)} doesn't print
                      {hiddenCount === 1 ? " it" : " them"}
                    </div>
                  )
                }

              </div>

            </div>

            {/* generate */}

            <div className="panel">

              <div className="panel-head">Generate</div>

              <div className="panel-body">

                {
                  loading

                    // While the conversion runs the checklist has nothing
                    // left to say — swap it for the leg being flown.
                    ? (
                      <div className="flightstrip" aria-live="polite">

                        <div className="fs-route">

                          <span className="fs-node dep">
                            {form.departure || "DEP"}
                          </span>

                          <span className="fs-line" aria-hidden="true">
                            <i className="fs-plane" />
                          </span>

                          <span className="fs-node arr">
                            {form.destination || "ARR"}
                          </span>

                        </div>

                        <div className="fs-stages">
                          {
                            STAGES.map((label, index) => (

                              <div
                                key={label}
                                className={
                                  "fs-stage"
                                  + (index < stage ? " done" : "")
                                  + (index === stage ? " live" : "")
                                }
                              >
                                <i />
                                {label}
                              </div>

                            ))
                          }
                        </div>

                      </div>
                    )

                    : (
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
                    )
                }

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

          )
        }

      </div>

    </div>

  );

}

export default Dashboard;
