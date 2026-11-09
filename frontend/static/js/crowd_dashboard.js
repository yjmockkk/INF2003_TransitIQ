const lineNames = {
  CCL: "Circle Line",
  CEL: "Circle Line Extension",
  CGL: "Changi Extension",
  DTL: "Downtown Line",
  EWL: "East West Line",
  NEL: "North East Line",
  NSL: "North South Line",
  BPL: "Bukit Panjang LRT",
  SLRT: "Sengkang LRT",
  PLRT: "Punggol LRT",
  TEL: "Thomson-East Coast Line",
};

const crowdNames = {
  l: "Low",
  m: "Moderate",
  h: "High",
  NA: "Not available",
};

const results = document.getElementById("results");
const message = document.getElementById("message");
const summary = document.getElementById("summary");

let observations = [];
let loading = false;
let hasLoaded = false;

function formatTime(value) {
  if (!value) return "Not available";

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return "Not available";
  }

  return date.toLocaleString("en-SG", {
    timeZone: "Asia/Singapore",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  });
}

function appendCell(row, value) {
  const cell = document.createElement("td");
  cell.textContent = value;
  row.appendChild(cell);
}

function displayRows() {
  const line = document.getElementById("line").value;
  const station = document.getElementById("station").value.trim().toUpperCase();
  const crowd = document.getElementById("crowd").value;

  const filtered = observations.filter(
    (item) =>
      (!line || item.line_code === line) &&
      (!station || item.station_code.toUpperCase().includes(station)) &&
      (!crowd || item.crowd_level === crowd),
  );

  filtered.sort(
    (a, b) =>
      a.line_code.localeCompare(b.line_code) ||
      a.station_code.localeCompare(b.station_code, "en", { numeric: true }),
  );

  results.replaceChildren();

  for (const item of filtered) {
    const row = document.createElement("tr");

    const values = [
      item.station_code,
      lineNames[item.line_code] || item.line_code,
      crowdNames[item.crowd_level] || "Not available",
      `${formatTime(item.start_time)} – ${formatTime(item.end_time)}`,
      formatTime(item.fetched_at),
    ];

    for (const value of values) {
      appendCell(row, value);
    }

    results.appendChild(row);
  }

  if (!filtered.length) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 5;
    cell.textContent = hasLoaded
      ? "No station observations match your selection."
      : "No station information loaded yet.";

    row.appendChild(cell);
    results.appendChild(row);
  }

  const counts = { l: 0, m: 0, h: 0, NA: 0 };

  for (const item of filtered) {
    const level = Object.hasOwn(counts, item.crowd_level)
      ? item.crowd_level
      : "NA";

    counts[level]++;
  }

  summary.textContent =
    `Showing ${filtered.length} station readings: ` +
    `${counts.l} Low | ` +
    `${counts.m} Moderate | ` +
    `${counts.h} High | ` +
    `${counts.NA} Not available`;
}

async function refreshData() {
  if (loading) return;

  loading = true;
  document.getElementById("refresh").disabled = true;
  message.textContent = "Loading station information...";

  try {
    const response = await fetch("/api/crowd/latest", {
      cache: "no-store",
    });

    const body = await response.json();

    if (!response.ok) {
      throw new Error("Unable to load station information.");
    }

    if (!Array.isArray(body.data)) {
      throw new Error("Unexpected station information received.");
    }

    observations = body.data;
    hasLoaded = true;
    displayRows();

    message.textContent = "";
    document.getElementById("refresh-time").textContent =
      "Display refreshed: " + formatTime(new Date());
  } catch (error) {
    message.textContent = hasLoaded
      ? "Could not refresh. Previously loaded information is still shown."
      : "Station information is unavailable. Please try again.";
  } finally {
    loading = false;
    document.getElementById("refresh").disabled = false;
  }
}

document.getElementById("line").addEventListener("change", displayRows);

document.getElementById("crowd").addEventListener("change", displayRows);

document.getElementById("station").addEventListener("input", displayRows);

document.getElementById("reset").addEventListener("click", () => {
  document.getElementById("line").value = "";
  document.getElementById("station").value = "";
  document.getElementById("crowd").value = "";
  displayRows();
});

document.getElementById("refresh").addEventListener("click", refreshData);

setInterval(() => {
  if (!document.hidden) refreshData();
}, 60000);

const busyForm = document.getElementById("busy-hours-form");
const busyButton = document.getElementById("busy-hours-button");
const busyMessage = document.getElementById("busy-hours-message");
const busySummary = document.getElementById("busy-hours-summary");
const busyResults = document.getElementById("busy-hours-results");

function busyHourLabel(hour) {
  const period = hour >= 12 ? "PM" : "AM";
  const displayHour = hour % 12 || 12;
  return `${displayHour}:00 ${period}`;
}

busyForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const station = document
    .getElementById("busy-station")
    .value.trim()
    .toUpperCase();

  busyButton.disabled = true;
  busyMessage.textContent = "Loading busy-hour information...";
  busySummary.textContent = "";
  busyResults.replaceChildren();

  try {
    const params = new URLSearchParams({
      station_code: station,
    });

    const response = await fetch("/api/crowd/busy-hours?" + params.toString(), {
      cache: "no-store",
    });

    const body = await response.json();

    if (!response.ok) {
      throw new Error(body.error || "Unable to load busy-hour information.");
    }

    if (!Array.isArray(body.data)) {
      throw new Error("Unexpected response received.");
    }

    const rows = body.data
      .filter((item) => item.hour >= 6 && item.hour <= 23)
      .sort(
        (a, b) => a.line_code.localeCompare(b.line_code) || a.hour - b.hour,
      );

    if (rows.length === 0) {
      busyMessage.textContent =
        "No available crowd observations between 6 AM " +
        "and 11 PM were found for this station.";
      return;
    }

    for (const item of rows) {
      const row = document.createElement("tr");

      appendCell(row, station);
      appendCell(row, item.line_code);
      appendCell(row, busyHourLabel(item.hour));
      appendCell(
        row,
        item.high_percentage < 10
          ? "Less than 10%"
          : item.high_percentage + "%",
      );

      busyResults.appendChild(row);
    }

    const maximum = Math.max(...rows.map((item) => item.high_percentage));

    if (maximum === 0) {
      busySummary.textContent =
        "No high crowd levels were recorded for this " +
        "station during the displayed hours.";
    } else {
      const busiest = rows
        .filter((item) => item.high_percentage === maximum)
        .map((item) => item.line_code + " at " + busyHourLabel(item.hour));

      busySummary.textContent =
        "Most frequently crowded: " +
        busiest.join(", ") +
        ". High crowd levels were reported in " +
        maximum +
        "% of observations at " +
        (busiest.length === 1 ? "this hour." : "these hours.");
    }

    busyMessage.textContent =
      "Historical results for " +
      station +
      ", showing 6 AM–11 PM Singapore time.";
  } catch (error) {
    busyMessage.textContent = error.message;
  } finally {
    busyButton.disabled = false;
  }
});

refreshData();
