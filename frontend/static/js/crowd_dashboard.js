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
const refreshButton = document.getElementById("refresh");

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

    appendCell(row, item.station_code);
    appendCell(row, lineNames[item.line_code] || item.line_code);
    appendCell(row, crowdNames[item.crowd_level] || "Not available");
    appendCell(
      row,
      `${formatTime(item.start_time)} – ${formatTime(item.end_time)}`,
    );
    appendCell(row, formatTime(item.fetched_at));

    results.appendChild(row);
  }

  if (filtered.length === 0) {
    const row = document.createElement("tr");
    const cell = document.createElement("td");

    cell.colSpan = 5;
    cell.textContent = hasLoaded
      ? "No station observations match your selection."
      : "No station information loaded yet.";

    row.appendChild(cell);
    results.appendChild(row);
  }

  const counts = {
    l: 0,
    m: 0,
    h: 0,
    NA: 0,
  };

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
  refreshButton.disabled = true;
  message.textContent = "Loading station information...";

  try {
    const response = await fetch("/api/crowd/latest", {
      cache: "no-store",
    });

    const body = await response.json();

    if (!response.ok) {
      throw new Error(body.error || "Unable to load station information.");
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
    refreshButton.disabled = false;
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

refreshButton.addEventListener("click", refreshData);

setInterval(() => {
  if (!document.hidden) {
    refreshData();
  }
}, 60000);

const busySearchForm = document.getElementById("busy-hours-form");
const busySearchInput = document.getElementById("busy-search");
const busySearchButton = document.getElementById("busy-search-button");
const busySearchMessage = document.getElementById("busy-message");
const busyTableContainer = document.getElementById("busy-tables");

const stationChoiceContainer = document.getElementById(
  "station-choice-container",
);
const stationChoice = document.getElementById("station-choice");

let busyStationOptions = [];
let busySearchLoading = false;

function setBusySearchLoading(value) {
  busySearchLoading = value;
  busySearchInput.disabled = value;
  busySearchButton.disabled = value;
  stationChoice.disabled = value;
}

function formatBusyHour(hour) {
  const period = hour >= 12 ? "PM" : "AM";
  return `${hour % 12 || 12}:00 ${period}`;
}

function formatBusyPercentage(value) {
  return value < 10 ? "Less than 10%" : `${value}%`;
}

function formatStationName(station) {
  return [station.station_name_english, station.station_name_chinese]
    .filter(Boolean)
    .join(" / ");
}

async function fetchBusyJson(url) {
  const response = await fetch(url, {
    cache: "no-store",
  });

  const body = await response.json();

  if (!response.ok) {
    throw new Error(body.error || "Unable to load information.");
  }

  return body;
}

function resetBusySearchResults() {
  busyTableContainer.replaceChildren();
  busySearchMessage.textContent = "";

  stationChoiceContainer.hidden = true;

  stationChoice.replaceChildren(new Option("Select a station", ""));

  busyStationOptions = [];
}

async function resolveBusyStation(station) {
  const body = await fetchBusyJson(
    "/api/train/stations/" + encodeURIComponent(station.station_code),
  );

  const details = body.data;

  if (!details || !Array.isArray(details.lines)) {
    throw new Error("Unexpected station details received.");
  }

  const stationLines = new Map();

  function addStationLine(code, line) {
    const key = code + ":" + line.line_code;

    stationLines.set(key, {
      station_code: code,
      line_code: line.line_code,
      line_name_english: line.line_name_english,
    });
  }

  for (const line of details.lines) {
    addStationLine(details.station_code, line);
  }

  for (const other of details.interchange_with || []) {
    addStationLine(other.station_code, other);
  }

  return {
    name: formatStationName(details),
    lines: Array.from(stationLines.values()).sort(
      (a, b) =>
        a.line_code.localeCompare(b.line_code) ||
        a.station_code.localeCompare(b.station_code, "en", { numeric: true }),
    ),
  };
}

async function populateBusyLineTable(station, section, status) {
  try {
    const params = new URLSearchParams({
      station_code: station.station_code,
      line_code: station.line_code,
    });

    const body = await fetchBusyJson(
      "/api/crowd/busy-hours?" + params.toString(),
    );

    if (!Array.isArray(body.data)) {
      throw new Error("Unexpected crowd information received.");
    }

    const rows = body.data
      .filter((item) => item.hour >= 6 && item.hour <= 23)
      .sort((a, b) => a.hour - b.hour);

    if (rows.length === 0) {
      status.textContent =
        "No crowd history is available for this station code.";

      return false;
    }

    status.textContent = "6 AM–11 PM Singapore time.";

    const wrapper = document.createElement("div");
    wrapper.style.overflowX = "auto";

    const table = document.createElement("table");
    table.setAttribute("border", "1");
    table.setAttribute("cellpadding", "10");
    table.setAttribute("cellspacing", "0");

    const caption = document.createElement("caption");
    caption.textContent =
      "Recorded high-crowd frequency for " +
      station.station_code +
      " / " +
      station.line_code;

    const thead = document.createElement("thead");
    const headerRow = document.createElement("tr");

    for (const title of [
      "Station code",
      "Line",
      "Time (Singapore)",
      "How often was it crowded?",
    ]) {
      const heading = document.createElement("th");
      heading.scope = "col";
      heading.textContent = title;

      headerRow.appendChild(heading);
    }

    thead.appendChild(headerRow);

    const tbody = document.createElement("tbody");

    for (const item of rows) {
      const row = document.createElement("tr");

      appendCell(row, station.station_code);
      appendCell(row, station.line_code);
      appendCell(row, formatBusyHour(item.hour));
      appendCell(row, formatBusyPercentage(item.high_percentage));

      tbody.appendChild(row);
    }

    table.append(caption, thead, tbody);
    wrapper.appendChild(table);
    section.appendChild(wrapper);

    return true;
  } catch (error) {
    // Other interchange tables can still load successfully.
    status.textContent =
      "Unable to load this station-line table: " + error.message;

    return false;
  }
}

async function displayBusyStation(station, codeOnly = false) {
  busyTableContainer.replaceChildren();

  busySearchMessage.textContent = "Loading station crowd history...";

  const resolved = codeOnly
    ? {
        name: formatStationName(station),
        lines: [
          {
            station_code: station.station_code,
            line_code: station.line_code,
            line_name_english: station.line_name_english,
          },
        ],
      }
    : await resolveBusyStation(station);

  if (resolved.lines.length === 0) {
    busySearchMessage.textContent =
      "No train lines were found for this station.";

    return;
  }

  // Create every section before fetching to preserve their order.
  const sections = resolved.lines.map((line) => {
    const section = document.createElement("section");
    const heading = document.createElement("h3");
    const status = document.createElement("p");

    heading.textContent =
      resolved.name +
      " — " +
      (line.line_name_english || line.line_code) +
      " (" +
      line.station_code +
      ")";

    status.textContent = "Loading...";

    section.append(heading, status);
    busyTableContainer.appendChild(section);

    return {
      line,
      section,
      status,
    };
  });

  await Promise.all(
    sections.map(({ line, section, status }) =>
      populateBusyLineTable(line, section, status),
    ),
  );

  busySearchMessage.textContent = "";
}

busySearchForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (busySearchLoading || !busySearchForm.reportValidity()) {
    return;
  }

  const query = busySearchInput.value.trim();

  if (!query) {
    busySearchInput.setCustomValidity("Enter a station name or code.");
    busySearchInput.reportValidity();

    return;
  }

  setBusySearchLoading(true);
  resetBusySearchResults();

  busySearchMessage.textContent = "Searching stations...";

  try {
    // This existing SQL API searches names and codes.
    const params = new URLSearchParams({
      q: query,
      limit: "500",
    });

    const body = await fetchBusyJson(
      "/api/train/stations?" + params.toString(),
    );

    if (!Array.isArray(body.data)) {
      throw new Error("Unexpected station search response.");
    }

    // Prefer an exact name or code match over partial matches.
    const normalized = query.toLowerCase();
    const exactCodeMatch = body.data.find(
      (station) => station.station_code.toLowerCase() === normalized,
    );

    if (exactCodeMatch) {
      await displayBusyStation(exactCodeMatch, true);
      return;
    }

    const exactMatches = body.data.filter((station) =>
      [
        station.station_code,
        station.station_name_english,
        station.station_name_chinese,
      ].some((value) => String(value || "").toLowerCase() === normalized),
    );

    const matches = exactMatches.length > 0 ? exactMatches : body.data;

    const uniqueStations = new Map();

    for (const station of matches) {
      const key = station.station_name_english;

      if (!uniqueStations.has(key)) {
        uniqueStations.set(key, station);
      }
    }

    busyStationOptions = Array.from(uniqueStations.values());

    if (busyStationOptions.length === 0) {
      busySearchMessage.textContent =
        "No stations found. Try an English name, " +
        "Chinese name, or station code.";

      return;
    }

    if (busyStationOptions.length === 1) {
      await displayBusyStation(busyStationOptions[0]);

      return;
    }

    busyStationOptions.forEach((station, index) => {
      stationChoice.add(new Option(formatStationName(station), String(index)));
    });

    stationChoiceContainer.hidden = false;

    busySearchMessage.textContent =
      "Several stations matched. Choose a station below.";
  } catch (error) {
    busySearchMessage.textContent = error.message;
  } finally {
    setBusySearchLoading(false);
  }
});

stationChoice.addEventListener("change", async () => {
  if (busySearchLoading || stationChoice.value === "") {
    return;
  }

  const station = busyStationOptions[Number(stationChoice.value)];

  if (!station) return;

  setBusySearchLoading(true);

  try {
    await displayBusyStation(station);
  } catch (error) {
    busySearchMessage.textContent = error.message;
  } finally {
    setBusySearchLoading(false);
  }
});

busySearchInput.addEventListener("input", () => {
  busySearchInput.setCustomValidity("");
  resetBusySearchResults();
});

// Initial load of the latest crowd table.
refreshData();
