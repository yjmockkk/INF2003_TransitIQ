const tabs = Array.from(
    document.querySelectorAll('.crowd-tabs [role="tab"]')
);

function activateTab(selectedTab) {
    for (const tab of tabs) {
        const selected = tab === selectedTab;

        tab.setAttribute("aria-selected", String(selected));
        tab.tabIndex = selected ? 0 : -1;

        const panel = document.getElementById(
            tab.getAttribute("aria-controls")
        );

        panel.hidden = !selected;
    }
}

tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => {
        activateTab(tab);
    });

    tab.addEventListener("keydown", event => {
        let nextIndex;

        switch (event.key) {
            case "ArrowRight":
                nextIndex = (index + 1) % tabs.length;
                break;

            case "ArrowLeft":
                nextIndex = (index - 1 + tabs.length) % tabs.length;
                break;

            case "Home":
                nextIndex = 0;
                break;

            case "End":
                nextIndex = tabs.length - 1;
                break;

            default:
                return;
        }

        event.preventDefault();

        tabs[nextIndex].focus();
        activateTab(tabs[nextIndex]);
    });
});