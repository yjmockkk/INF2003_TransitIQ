const statusElement = document.getElementById("train-alert-status");
const errorElement = document.getElementById("train-alert-error");
const detailsElement = document.getElementById("train-alert-details");
const checkedElement = document.getElementById("train-alert-checked");
const refreshButton = document.getElementById("train-alert-refresh");

const lineNames = {
    EWL: "East West Line, including Changi Extension",
    NSL: "North South Line",
    NEL: "North East Line",
    CCL: "Circle Line, including Circle Line Extension",
    DTL: "Downtown Line",
    TEL: "Thomson-East Coast Line",
    BPL: "Bukit Panjang LRT",
    STL: "Sengkang LRT",
    PTL: "Punggol LRT"
};

const segmentFields = [
    ["Line", "Line"],
    ["Direction", "Affected direction"],
    ["Stations", "Affected station codes"],
    ["FreePublicBus", "Free public bus services"],
    ["FreeMRTShuttle", "Free MRT shuttle services"],
    ["MRTShuttleDirection", "MRT shuttle direction"]
];

let loading = false;
let hasLoaded = false;

function displayTrainStatus(status) {
    const settings = {
        "1": {
            text: "Trains are running. Minor delays may occur.",
            className: "train-status--normal"
        },
        "2": {
            text: "Train services are disrupted or experiencing major delays.",
            className: "train-status--disrupted"
        }
    };

    const selected = settings[String(status)] || {
        text: "Train-service information is unavailable.",
        className: "train-status--unknown"
    };

    statusElement.textContent = selected.text;

    statusElement.classList.remove(
        "train-status--normal",
        "train-status--disrupted",
        "train-status--unknown"
    );

    statusElement.classList.add(
        "train-status",
        selected.className
    );
}

function isObject(value) {
    return (
        value !== null &&
        typeof value === "object" &&
        !Array.isArray(value)
    );
}

function hasContent(value) {
    if (value === null || value === undefined) return false;

    if (typeof value === "string") {
        return value.trim() !== "";
    }

    if (Array.isArray(value)) {
        return value.some(hasContent);
    }

    if (isObject(value)) {
        return Object.values(value).some(hasContent);
    }

    return true;
}

function asItems(value) {
    const items = Array.isArray(value) ? value : [value];
    return items.filter(hasContent);
}

function valueText(value) {
    if (!hasContent(value)) return "Not provided";

    if (typeof value === "object") {
        return JSON.stringify(value, null, 2);
    }

    return String(value);
}

function formatCheckedTime(value) {
    if (typeof value !== "string" || !value) {
        return "Not available";
    }

    const date = new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "Not available";
    }

    return date.toLocaleString("en-SG", {
        timeZone: "Asia/Singapore",
        day: "numeric",
        month: "short",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true
    });
}

function createCard() {
    const card = document.createElement("article");

    card.style.border = "1px solid #ccc";
    card.style.padding = "12px";
    card.style.marginBottom = "12px";
    card.style.overflowWrap = "anywhere";

    return card;
}

function appendField(list, label, value) {
    if (!hasContent(value)) return;

    const term = document.createElement("dt");
    term.textContent = label;

    const description = document.createElement("dd");
    description.textContent = valueText(value);
    description.style.whiteSpace = "pre-wrap";

    list.append(term, description);
}

// Preserve unfamiliar fields without guessing what they mean.
function appendAdditionalDetails(parent, value, knownKeys = []) {
    if (!isObject(value)) return;

    const additional = Object.fromEntries(
        Object.entries(value).filter(([key, entry]) =>
            !knownKeys.includes(key) && hasContent(entry)
        )
    );

    if (Object.keys(additional).length === 0) return;

    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const content = document.createElement("pre");

    summary.textContent = "Additional information";
    content.textContent = JSON.stringify(additional, null, 2);
    content.style.whiteSpace = "pre-wrap";
    content.style.overflowWrap = "anywhere";

    details.append(summary, content);
    parent.appendChild(details);
}

function renderAffectedSegment(segment, index, multiple) {
    const card = createCard();

    if (multiple) {
        const heading = document.createElement("h4");
        heading.textContent = `Affected segment ${index + 1}`;
        card.appendChild(heading);
    }

    if (!isObject(segment)) {
        card.textContent = valueText(segment);
        return card;
    }

    const list = document.createElement("dl");

    for (const [key, label] of segmentFields) {
        let value = segment[key];

        if (key === "Line" && typeof value === "string") {
            const name = lineNames[value];
            value = name ? `${name} (${value})` : value;
        }

        if (
            (key === "Direction" || key === "MRTShuttleDirection") &&
            typeof value === "string"
        ) {
            const direction = value.trim();

            value = direction.toLowerCase() === "both"
                ? "Both directions"
                : direction
                    ? `Towards ${direction}`
                    : "";
        }

        // Preserve station/shuttle strings, including | and ; separators.
        appendField(list, label, value);
    }

    card.appendChild(list);

    appendAdditionalDetails(
        card,
        segment,
        segmentFields.map(([key]) => key)
    );

    return card;
}

function renderMessage(message, index, multiple) {
    const card = createCard();

    if (multiple) {
        const heading = document.createElement("h4");
        heading.textContent = `Advisory ${index + 1}`;
        card.appendChild(heading);
    }

    if (!isObject(message)) {
        card.textContent = valueText(message);
        return card;
    }

    if (hasContent(message.Content)) {
        const content = document.createElement("p");
        content.textContent = valueText(message.Content);
        content.style.whiteSpace = "pre-wrap";
        card.appendChild(content);
    }

    if (hasContent(message.CreatedDate)) {
        const reported = document.createElement("p");

        reported.textContent =
            "Published: " + valueText(message.CreatedDate) +
            " (as provided by LTA)";

        card.appendChild(reported);
    }

    appendAdditionalDetails(
        card,
        message,
        ["Content", "CreatedDate"]
    );

    return card;
}

function buildAlertContent(data) {
    const fragment = document.createDocumentFragment();
    const messages = asItems(data.messages);
    const segments = asItems(data.affected_segments);

    // Messages are displayed regardless of the overall status.
    if (messages.length > 0) {
        const section = document.createElement("section");
        const heading = document.createElement("h3");
        heading.textContent = "Travel advisories";

        section.appendChild(heading);

        messages.forEach((message, index) => {
            section.appendChild(
                renderMessage(message, index, messages.length > 1)
            );
        });

        fragment.appendChild(section);
    }

    if (segments.length > 0) {
        const section = document.createElement("section");
        const heading = document.createElement("h3");
        heading.textContent = "Affected services and travel arrangements";

        section.appendChild(heading);

        segments.forEach((segment, index) => {
            section.appendChild(
                renderAffectedSegment(
                    segment,
                    index,
                    segments.length > 1
                )
            );
        });

        fragment.appendChild(section);
    }

    if (
        String(data.status) === "2" &&
        messages.length === 0 &&
        segments.length === 0
    ) {
        const note = document.createElement("p");
        note.textContent =
            "A disruption or major delay is reported. " +
            "Further details have not been provided.";

        fragment.appendChild(note);
    }

    appendAdditionalDetails(fragment, data.additional_details);

    return fragment;
}

async function refreshTrainAlerts() {
    if (loading) return;

    loading = true;
    refreshButton.disabled = true;
    errorElement.textContent = "";

    try {
        const response = await fetch("/api/crowd/alerts/latest", {
            cache: "no-store"
        });

        if (!response.ok) {
            throw new Error("Unable to refresh train-service information.");
        }

        const body = await response.json();

        if (!isObject(body) || !Object.hasOwn(body, "data")) {
            throw new Error("Unexpected train-service response.");
        }

        if (body.data === null) {
            statusElement.textContent =
                "No train-service information has been collected yet.";

            detailsElement.replaceChildren();
            checkedElement.textContent = "";
            hasLoaded = false;
            return;
        }

        const data = body.data;

        if (!isObject(data)) {
            throw new Error("Unexpected train-service response.");
        }

        // Build before replacing the previous display.
        const content = buildAlertContent(data);

        displayTrainStatus(data.status);

        detailsElement.replaceChildren(content);

        checkedElement.textContent =
            "Last checked: " +
            formatCheckedTime(data.last_checked) +
            " (Singapore time)";

        hasLoaded = true;

    } catch (error) {
        errorElement.textContent = hasLoaded
            ? "Could not refresh. Previously loaded information is shown; " +
              "check the last-checked time."
            : "Train-service information is temporarily unavailable.";

        if (!hasLoaded) {
            statusElement.textContent = "Service status unavailable";
        }

        console.error("Train-service refresh failed:", error.message);

    } finally {
        loading = false;
        refreshButton.disabled = false;
    }
}

refreshButton.addEventListener("click", refreshTrainAlerts);

refreshTrainAlerts();

setInterval(() => {
    if (!document.hidden) {
        refreshTrainAlerts();
    }
}, 60000);