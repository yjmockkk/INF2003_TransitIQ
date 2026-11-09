// Latest crowd table, station names, filters, and refresh.
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
    TEL: "Thomson-East Coast Line"
};

const crowdNames = {
    l: "Low",
    m: "Moderate",
    h: "High",
    NA: "Not available"
};

const results = document.getElementById("results");
const message = document.getElementById("message");
const summary = document.getElementById("summary");
const refreshButton = document.getElementById("refresh");
const refreshTime = document.getElementById("refresh-time");

const lineFilter = document.getElementById("line");
const stationFilter = document.getElementById("station");
const crowdFilter = document.getElementById("crowd");
const resetButton = document.getElementById("reset");

const stationNameLookup = new Map();

let observations = [];
let loading = false;
let hasLoaded = false;

function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.appendChild(cell);
}

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
        hour12: true
    });
}

async function fetchJson(url) {
    const response = await fetch(url, {
        cache: "no-store"
    });

    const body = await response.json();

    if (!response.ok) {
        throw new Error(
            body.error || "Unable to load information."
        );
    }

    return body;
}

async function loadStationNames() {
    const limit = 500;
    let offset = 0;
    const names = new Map();

    while (true) {
        const params = new URLSearchParams({
            limit: String(limit),
            offset: String(offset)
        });

        const body = await fetchJson(
            "/api/train/stations?" + params.toString()
        );

        if (!Array.isArray(body.data)) {
            throw new Error("Unexpected station information received.");
        }

        for (const station of body.data) {
            const name = [
                station.station_name_english,
                station.station_name_chinese
            ].filter(Boolean).join(" / ");

            names.set(
                station.station_code.toUpperCase(),
                name
            );
        }

        if (body.data.length < limit) break;

        offset += limit;
    }

    stationNameLookup.clear();

    for (const [code, name] of names) {
        stationNameLookup.set(code, name);
    }
}

function displayRows() {
    const line = lineFilter.value;
    const station = stationFilter.value.trim().toUpperCase();
    const crowd = crowdFilter.value;

    const filtered = observations.filter(item =>
        (!line || item.line_code === line) &&
        (!station ||
            item.station_code.toUpperCase().includes(station)) &&
        (!crowd || item.crowd_level === crowd)
    );

    filtered.sort((a, b) =>
        a.line_code.localeCompare(b.line_code) ||
        a.station_code.localeCompare(
            b.station_code,
            "en",
            { numeric: true }
        )
    );

    results.replaceChildren();

    for (const item of filtered) {
        const row = document.createElement("tr");

        appendCell(row, item.station_code);

        appendCell(
            row,
            stationNameLookup.get(
                item.station_code.toUpperCase()
            ) || "Not available"
        );

        appendCell(
            row,
            lineNames[item.line_code] || item.line_code
        );

        appendCell(
            row,
            crowdNames[item.crowd_level] || "Not available"
        );

        appendCell(
            row,
            `${formatTime(item.start_time)} – ${formatTime(item.end_time)}`
        );

        appendCell(row, formatTime(item.fetched_at));

        results.appendChild(row);
    }

    if (filtered.length === 0) {
        const row = document.createElement("tr");
        const cell = document.createElement("td");

        cell.colSpan = 6;
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
        NA: 0
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
        const body = await fetchJson("/api/crowd/latest");

        if (!Array.isArray(body.data)) {
            throw new Error("Unexpected crowd information received.");
        }

        observations = body.data;
        hasLoaded = true;

        displayRows();

        message.textContent = "";
        refreshTime.textContent =
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

lineFilter.addEventListener("change", displayRows);
crowdFilter.addEventListener("change", displayRows);
stationFilter.addEventListener("input", displayRows);

resetButton.addEventListener("click", () => {
    lineFilter.value = "";
    stationFilter.value = "";
    crowdFilter.value = "";

    displayRows();
});

refreshButton.addEventListener("click", refreshData);

setInterval(() => {
    if (!document.hidden) {
        refreshData();
    }
}, 60000);

// Load crowd readings immediately.
refreshData();

// Add station names when the SQL lookup is available.
loadStationNames()
    .then(() => {
        if (hasLoaded) {
            displayRows();
        }
    })
    .catch(error => {
        console.error("Station-name lookup failed:", error.message);
    });