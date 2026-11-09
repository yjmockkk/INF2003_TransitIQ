// Station-name/code search and separate interchange tables.

const searchForm = document.getElementById("busy-hours-form");
const searchInput = document.getElementById("busy-search");
const searchButton = document.getElementById("busy-search-button");
const searchMessage = document.getElementById("busy-message");
const tableContainer = document.getElementById("busy-tables");

const choiceContainer = document.getElementById(
    "station-choice-container"
);
const stationChoice = document.getElementById("station-choice");

let stationOptions = [];
let loading = false;

function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value;
    row.appendChild(cell);
}

function setLoading(value) {
    loading = value;
    searchInput.disabled = value;
    searchButton.disabled = value;
    stationChoice.disabled = value;
}

function formatHour(hour) {
    const period = hour >= 12 ? "PM" : "AM";
    return `${hour % 12 || 12}:00 ${period}`;
}

function formatPercentage(value) {
    return value < 10 ? "Less than 10%" : `${value}%`;
}

function formatStationName(station) {
    return [
        station.station_name_english,
        station.station_name_chinese
    ].filter(Boolean).join(" / ");
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

function resetResults() {
    tableContainer.replaceChildren();
    searchMessage.textContent = "";

    choiceContainer.hidden = true;
    stationChoice.replaceChildren(
        new Option("Select a station", "")
    );

    stationOptions = [];
}

// Used for name searches: find all interchange codes.
async function resolveStation(station) {
    const body = await fetchJson(
        "/api/train/stations/" +
        encodeURIComponent(station.station_code)
    );

    const details = body.data;

    if (!details || !Array.isArray(details.lines)) {
        throw new Error("Unexpected station details received.");
    }

    const stationLines = new Map();

    function addLine(code, line) {
        const key = code + ":" + line.line_code;

        stationLines.set(key, {
            station_code: code,
            line_code: line.line_code,
            line_name_english: line.line_name_english
        });
    }

    for (const line of details.lines) {
        addLine(details.station_code, line);
    }

    for (const other of details.interchange_with || []) {
        addLine(other.station_code, other);
    }

    return {
        name: formatStationName(details),
        lines: Array.from(stationLines.values()).sort((a, b) =>
            a.line_code.localeCompare(b.line_code) ||
            a.station_code.localeCompare(
                b.station_code,
                "en",
                { numeric: true }
            )
        )
    };
}

async function populateLineTable(station, section, status) {
    try {
        const params = new URLSearchParams({
            station_code: station.station_code,
            line_code: station.line_code
        });

        const body = await fetchJson(
            "/api/crowd/busy-hours?" + params.toString()
        );

        if (!Array.isArray(body.data)) {
            throw new Error("Unexpected crowd information received.");
        }

        const rows = body.data
            .filter(item =>
                item.hour >= 6 &&
                item.hour <= 23
            )
            .sort((a, b) => a.hour - b.hour);

        if (rows.length === 0) {
            status.textContent =
                "No crowd history is available for this station code.";
            return;
        }

        status.textContent = "6 AM–11 PM Singapore time.";

        const wrapper = document.createElement("div");
        wrapper.style.overflowX = "auto";

        const table = document.createElement("table");
        table.setAttribute("border", "1");
        table.setAttribute("cellpadding", "10");
        table.setAttribute("cellspacing", "0");

        const thead = document.createElement("thead");
        const headerRow = document.createElement("tr");

        for (const title of [
            "Station code",
            "Line",
            "Time (Singapore)",
            "How often was it crowded?"
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
            appendCell(row, formatHour(item.hour));
            appendCell(
                row,
                formatPercentage(item.high_percentage)
            );

            tbody.appendChild(row);
        }

        table.append(thead, tbody);
        wrapper.appendChild(table);
        section.appendChild(wrapper);

    } catch (error) {
        // Keep other interchange tables visible if this one fails.
        status.textContent =
            "Unable to load this station-line table: " +
            error.message;
    }
}

async function displayStation(station, codeOnly = false) {
    tableContainer.replaceChildren();
    searchMessage.textContent = "Loading station crowd history...";

    const resolved = codeOnly
        ? {
            name: formatStationName(station),
            lines: [{
                station_code: station.station_code,
                line_code: station.line_code,
                line_name_english: station.line_name_english
            }]
        }
        : await resolveStation(station);

    if (resolved.lines.length === 0) {
        searchMessage.textContent =
            "No train lines were found for this station.";
        return;
    }

    const sections = resolved.lines.map(line => {
        const section = document.createElement("section");
        const heading = document.createElement("h3");
        const status = document.createElement("p");

        heading.textContent =
            resolved.name + " — " +
            (line.line_name_english || line.line_code) +
            " (" + line.station_code + ")";

        status.textContent = "Loading...";

        section.append(heading, status);
        tableContainer.appendChild(section);

        return { line, section, status };
    });

    await Promise.all(
        sections.map(({ line, section, status }) =>
            populateLineTable(line, section, status)
        )
    );

    searchMessage.textContent = "";
}

searchForm.addEventListener("submit", async event => {
    event.preventDefault();

    if (loading || !searchForm.reportValidity()) return;

    const query = searchInput.value.trim();

    if (!query) {
        searchInput.setCustomValidity(
            "Enter a station name or code."
        );
        searchInput.reportValidity();
        return;
    }

    setLoading(true);
    resetResults();

    searchMessage.textContent = "Searching stations...";

    try {
        const params = new URLSearchParams({
            q: query,
            limit: "500"
        });

        const body = await fetchJson(
            "/api/train/stations?" + params.toString()
        );

        if (!Array.isArray(body.data)) {
            throw new Error("Unexpected station search response.");
        }

        const normalized = query.toLowerCase();

        // Exact code: show only that code's table.
        const exactCodeMatch = body.data.find(station =>
            station.station_code.toLowerCase() === normalized
        );

        if (exactCodeMatch) {
            await displayStation(exactCodeMatch, true);
            return;
        }

        // Exact name: prefer it over partial-name matches.
        const exactMatches = body.data.filter(station =>
            [
                station.station_name_english,
                station.station_name_chinese
            ].some(value =>
                String(value || "").toLowerCase() === normalized
            )
        );

        const matches = exactMatches.length > 0
            ? exactMatches
            : body.data;

        const uniqueStations = new Map();

        for (const station of matches) {
            const key = station.station_name_english;

            if (!uniqueStations.has(key)) {
                uniqueStations.set(key, station);
            }
        }

        stationOptions = Array.from(uniqueStations.values());

        if (stationOptions.length === 0) {
            searchMessage.textContent =
                "No stations found. Try an English name, " +
                "Chinese name, or station code.";
            return;
        }

        if (stationOptions.length === 1) {
            await displayStation(stationOptions[0]);
            return;
        }

        stationOptions.forEach((station, index) => {
            stationChoice.add(
                new Option(
                    formatStationName(station),
                    String(index)
                )
            );
        });

        choiceContainer.hidden = false;
        searchMessage.textContent =
            "Several stations matched. Choose a station below.";

    } catch (error) {
        searchMessage.textContent = error.message;

    } finally {
        setLoading(false);
    }
});

stationChoice.addEventListener("change", async () => {
    if (loading || stationChoice.value === "") return;

    const station = stationOptions[
        Number(stationChoice.value)
    ];

    if (!station) return;

    setLoading(true);

    try {
        await displayStation(station);
    } catch (error) {
        searchMessage.textContent = error.message;
    } finally {
        setLoading(false);
    }
});

searchInput.addEventListener("input", () => {
    searchInput.setCustomValidity("");
    resetResults();
});