(() => {
    const header = document.querySelector(".site-header");
    const toggle = header?.querySelector(".nav-toggle");
    const menu = document.getElementById("header-actions");

    if (!header || !toggle || !menu) {
        return;
    }

    const mobile = window.matchMedia("(max-width: 650px)");

    function setOpen(open) {
        header.classList.toggle("menu-open", open);
        toggle.setAttribute("aria-expanded", String(open));
        toggle.setAttribute("aria-label", open ? "Zavřít menu" : "Otevřít menu");
    }

    toggle.addEventListener("click", () => {
        if (mobile.matches) {
            setOpen(toggle.getAttribute("aria-expanded") !== "true");
        }
    });

    header.addEventListener("keydown", (event) => {
        if (event.key === "Escape" && mobile.matches
            && toggle.getAttribute("aria-expanded") === "true") {
            setOpen(false);
            toggle.focus();
        }
    });

    menu.addEventListener("click", (event) => {
        if (mobile.matches && event.target.closest("a")) {
            setOpen(false);
            toggle.focus();
        }
    });

    mobile.addEventListener("change", () => {
        setOpen(false);
    });

    toggle.hidden = false;
    header.classList.add("nav-ready");
})();
