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

const fallbackStations = [
    ["CC18", "Bukit Brown", "武吉布朗", "CCL", "Circle Line"],
    ["CC30", "Keppel", "岌巴", "CCL", "Circle Line"],
    ["CC31", "Cantonment", "广东民", "CCL", "Circle Line"],
    ["CC32", "Prince Edward Road", "爱德华太子路", "CCL", "Circle Line"],
    ["CC33", "Marina Bay", "滨海湾", "CCL", "Circle Line"],
    ["CC34", "Bayfront", "海湾舫", "CCL", "Circle Line"],
    ["DT36", "Xilin", "锡林", "DTL", "Downtown Line"],
    ["DT37", "Sungei Bedok", "双溪勿洛", "DTL", "Downtown Line"],
    ["TE10", "Mount Pleasant", "快乐山", "TEL", "Thomson-East Coast Line"],
    ["TE21", "Marina South", "滨海南", "TEL", "Thomson-East Coast Line"],
    ["TE22A", "Founders’ Memorial", "建国先贤纪念园", "TEL", "Thomson-East Coast Line"],
    ["TE30", "Bedok South", "勿洛南", "TEL", "Thomson-East Coast Line"],
    ["TE31", "Sungei Bedok", "双溪勿洛", "TEL", "Thomson-East Coast Line"]
].map(([code, english, chinese, lineCode, lineName]) => ({
    station_code: code,
    station_name_english: english,
    station_name_chinese: chinese,
    line_code: lineCode,
    line_name_english: lineName
}));

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
    const fallback = fallbackStations.find(item =>
        item.station_code === station.station_code.toUpperCase()
    );

    if (fallback) {
        return {
            name: formatStationName(fallback),
            lines: fallbackStations
                .filter(item =>
                    item.station_name_english ===
                    fallback.station_name_english
                )
                .map(item => ({
                    station_code: item.station_code,
                    line_code: item.line_code,
                    line_name_english: item.line_name_english
                }))
        };
    }
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
    const stationAliases = {
        CE1: { station_code: "CC34", line_code: "CCL" },
        CE2: { station_code: "CC33", line_code: "CCL" }
    };

    const lineAliases = {
        CE: "CEL",
        CG: "CGL",
        STL: "SLRT",
        PTL: "PLRT"
    };

    const stationCode = station.station_code.trim().toUpperCase();
    const mappedStation = stationAliases[stationCode];

    const params = new URLSearchParams({
        station_code: mappedStation?.station_code || stationCode,
        line_code:
            mappedStation?.line_code ||
            lineAliases[station.line_code] ||
            station.line_code
    });


        const body = await fetchJson(
            "/api/crowd/busy-hours?" + params.toString()
        );

        if (!Array.isArray(body.data)) {
            throw new Error("Unexpected crowd information received.");
        }


        const observationsByHour = new Map();

        for (const item of body.data) {
            const hour = Number(item.hour);
            const raw = item.high_percentage;

            if (
                !Number.isInteger(hour) ||
                hour < 6 ||
                hour > 23 ||
                raw === null ||
                raw === undefined ||
                raw === ""
            ) {
                continue;
            }

            const percentage = Number(raw);

            if (
                Number.isFinite(percentage) &&
                percentage >= 0 &&
                percentage <= 100
            ) {
                observationsByHour.set(hour, percentage);
            }
        }

        if (observationsByHour.size === 0) {
            status.textContent =
                "No crowd history is available for this station code.";
            return;
        }

        status.textContent = "";

        const figure = document.createElement("figure");
        figure.className = "busy-chart";

        const header = document.createElement("div");
        header.className = "busy-chart-header";

        const summary = document.createElement("div");
        summary.className = "busy-chart-summary";

        const eyebrow = document.createElement("span");
        eyebrow.className = "busy-chart-eyebrow";
        eyebrow.textContent = "PEAK RECORDED HOUR";

        const peakValue = Math.max(...observationsByHour.values());

        const peakHours = Array.from(observationsByHour)
            .filter(([, value]) => value === peakValue)
            .map(([hour]) => formatHour(hour));

        const peakTime = document.createElement("strong");

        const peakDetail = document.createElement("span");
        peakDetail.className = "busy-chart-peak-detail";

        if (peakValue < 10) {
            eyebrow.textContent = "CROWD PATTERN";
            peakTime.textContent = "Low frequency across recorded hours";
            peakDetail.textContent =
                "Every available hour had fewer than 10% crowded observations.";
        } else {
            peakTime.textContent = peakHours.join(" · ");
            peakDetail.textContent =
                `${formatPercentage(peakValue)} of observations were crowded`;
        }

        summary.append(eyebrow, peakTime, peakDetail);

        const legend = document.createElement("div");
        legend.className = "busy-chart-legend";
        legend.setAttribute("aria-label", "Crowded observation frequency");

        for (const [className, label] of [
            ["low", "Below 25%"],
            ["medium", "25–49%"],
            ["high", "50% or more"]
        ]) {
            const entry = document.createElement("span");
            entry.className = "busy-chart-legend-item";

            const dot = document.createElement("span");
            dot.className = `busy-chart-dot busy-chart-dot--${className}`;
            dot.setAttribute("aria-hidden", "true");

            entry.append(dot, document.createTextNode(label));
            legend.appendChild(entry);
        }

        header.append(summary, legend);

        const caption = document.createElement("figcaption");
        caption.className = "busy-chart-caption";
        caption.textContent = "Crowded observations (%)";

        const scroll = document.createElement("div");
        scroll.className = "busy-chart-scroll";
        scroll.setAttribute("role", "region");
        scroll.setAttribute(
            "aria-label",
            `${station.station_code} ${station.line_code} hourly crowd chart`
        );

        const plot = document.createElement("div");
        plot.className = "busy-chart-plot";

        const axis = document.createElement("div");
        axis.className = "busy-chart-axis";
        axis.setAttribute("aria-hidden", "true");

        for (const percentage of [100, 75, 50, 25, 0]) {
            const label = document.createElement("span");
            label.textContent = `${percentage}%`;
            axis.appendChild(label);
        }

        const bars = document.createElement("div");
        bars.className = "busy-chart-bars";

        const detail = document.createElement("p");
        detail.className = "busy-chart-detail";
        detail.setAttribute("role", "status");

        const defaultDetail =
            "Singapore time · Select an hour to see its recorded crowd frequency.";

        detail.textContent = defaultDetail;

        for (let hour = 6; hour <= 23; hour++) {
            const hasData = observationsByHour.has(hour);
            const percentage = observationsByHour.get(hour);
            const isPeak = hasData && peakValue >= 10 && percentage === peakValue;

            const frequency = !hasData
                ? "missing"
                : percentage >= 50
                    ? "high"
                    : percentage >= 25
                        ? "medium"
                        : "low";

            const valueText = hasData
                ? formatPercentage(percentage)
                : "No data";

            const column = document.createElement("button");
            column.type = "button";
            column.className =
                `busy-chart-column busy-chart-column--${frequency}`;

            column.setAttribute(
                "aria-label",
                `${formatHour(hour)}: ${
                    hasData
                        ? `${valueText} of recorded observations were crowded`
                        : "No recorded data"
                }${isPeak ? ". Peak recorded hour." : ""}`
            );

            const marker = document.createElement("span");
            marker.className = "busy-chart-marker";
            marker.textContent = isPeak ? "PEAK" : "";
            marker.setAttribute("aria-hidden", "true");

            const track = document.createElement("span");
            track.className = "busy-chart-track";
            track.setAttribute("aria-hidden", "true");

            if (hasData) {
                const bar = document.createElement("span");
                bar.className = "busy-chart-bar";
                bar.style.height = `${percentage}%`;

                if (percentage === 0) {
                    bar.classList.add("busy-chart-bar--zero");
                }

                track.appendChild(bar);
            } else {
                const missing = document.createElement("span");
                missing.className = "busy-chart-missing";
                missing.textContent = "—";
                track.appendChild(missing);
            }

            const tooltip = document.createElement("span");
            tooltip.className = "busy-chart-tooltip";
            tooltip.textContent = valueText;
            tooltip.setAttribute("aria-hidden", "true");

            const hourLabel = document.createElement("span");
            hourLabel.className = "busy-chart-hour";
            hourLabel.textContent =
                `${hour % 12 || 12}${hour >= 12 ? "PM" : "AM"}`;
            hourLabel.setAttribute("aria-hidden", "true");

            function showDetail() {
                detail.textContent = hasData
                    ? `${formatHour(hour)} · ${valueText} of recorded observations were crowded.`
                    : `${formatHour(hour)} · No recorded data.`;
            }

            column.addEventListener("mouseenter", showDetail);
            column.addEventListener("focus", showDetail);
            column.addEventListener("click", showDetail);

            column.append(marker, track, tooltip, hourLabel);
            bars.appendChild(column);
        }

        plot.append(axis, bars);
        scroll.appendChild(plot);
        figure.append(header, caption, scroll, detail);
        section.appendChild(figure);

    } catch (error) {
        status.textContent =
            "Unable to load this station-line chart: " +
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

    if (tableContainer.firstElementChild) {
        tableContainer.scrollIntoView({
            behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
                ? "instant"
                : "smooth",
            block: "start"
        });
    }
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

        const fallbackMatches = fallbackStations.filter(station =>
            [
                station.station_code,
                station.station_name_english,
                station.station_name_chinese
            ].some(value =>
                value.toLowerCase().includes(normalized)
            )
        );

        const existingCodes = new Set(
            body.data.map(station =>
                station.station_code.toUpperCase()
            )
        );

        for (const station of fallbackMatches) {
            if (!existingCodes.has(station.station_code)) {
                body.data.push(station);
            }
        }

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