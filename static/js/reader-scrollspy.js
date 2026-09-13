document.addEventListener("DOMContentLoaded", () => {
    const content = document.getElementById("reader-content");

    const desktopToc = document.getElementById("reader-toc");
    const mobileToc = document.getElementById("reader-toc-mobile");

    const desktopTocSection = document.getElementById(
        "reader-toc-section"
    );

    const mobileDetails = document.getElementById(
        "reader-mobile-toc"
    );

    if (!content) {
        return;
    }


    const headings = Array.from(
        content.querySelectorAll("h2, h3")
    );


    /*
     * Pokud někdy Pandoc nebo ručně psané HTML
     * nevytvoří ID, vytvoříme ho automaticky.
     */
    const usedIds = new Set();


    function createSlug(text) {
        return text
            .toLowerCase()
            .normalize("NFD")
            .replace(/[\u0300-\u036f]/g, "")
            .replace(/[^a-z0-9]+/g, "-")
            .replace(/^-+|-+$/g, "");
    }


    headings.forEach((heading, index) => {
        let id = heading.id;

        if (!id) {
            id = createSlug(
                heading.textContent.trim()
            );

            if (!id) {
                id = `sekce-${index + 1}`;
            }
        }

        let uniqueId = id;
        let suffix = 2;

        while (usedIds.has(uniqueId)) {
            uniqueId = `${id}-${suffix}`;
            suffix++;
        }

        heading.id = uniqueId;

        usedIds.add(
            uniqueId
        );
    });


    /*
     * Pokud aktuální kapitola nemá žádné H2/H3,
     * schováme pouze její obsah.
     *
     * Sidebar samotný zůstává viditelný,
     * protože obsahuje navigaci mezi kapitolami.
     */
    if (headings.length === 0) {
        if (desktopTocSection) {
            desktopTocSection.hidden = true;
        }

        if (mobileDetails) {
            mobileDetails.hidden = true;
        }

        return;
    }


    /*
     * Bez těchto dvou kontejnerů není možné
     * obsah kapitoly sestavit.
     */
    if (!desktopToc || !mobileToc) {
        return;
    }


    const linksById = new Map();


    function registerLink(id, link) {
        if (!linksById.has(id)) {
            linksById.set(
                id,
                []
            );
        }

        linksById
            .get(id)
            .push(link);
    }


    function buildToc(container, mobile = false) {
        headings.forEach((heading) => {
            const link =
                document.createElement("a");

            link.href = `#${heading.id}`;

            link.textContent =
                heading.textContent.trim();

            link.classList.add(
                "reader-toc-link"
            );

            if (heading.tagName === "H3") {
                link.classList.add(
                    "reader-toc-link-subsection"
                );
            }

            registerLink(
                heading.id,
                link
            );

            if (mobile) {
                link.addEventListener(
                    "click",
                    () => {
                        if (mobileDetails) {
                            mobileDetails.removeAttribute(
                                "open"
                            );
                        }
                    }
                );
            }

            container.appendChild(
                link
            );
        });
    }


    buildToc(
        desktopToc
    );

    buildToc(
        mobileToc,
        true
    );


    let activeId = null;


    function setActive(id) {
        if (activeId === id) {
            return;
        }

        document
            .querySelectorAll(
                ".reader-toc-link.is-active"
            )
            .forEach((link) => {
                link.classList.remove(
                    "is-active"
                );

                link.removeAttribute(
                    "aria-current"
                );
            });


        const activeLinks =
            linksById.get(id) || [];


        activeLinks.forEach((link) => {
            link.classList.add(
                "is-active"
            );

            link.setAttribute(
                "aria-current",
                "location"
            );
        });


        activeId = id;
    }


    function updateActiveSection() {
        const offset = 150;

        let current =
            headings[0];


        for (const heading of headings) {
            const top =
                heading
                    .getBoundingClientRect()
                    .top;

            if (top <= offset) {
                current = heading;
            } else {
                break;
            }
        }


        /*
         * Pokud jsme úplně dole,
         * označíme poslední sekci.
         */
        const pageBottom =
            window.scrollY
            + window.innerHeight;

        const documentHeight =
            document
                .documentElement
                .scrollHeight;


        if (
            pageBottom
            >= documentHeight - 4
        ) {
            current =
                headings[
                    headings.length - 1
                ];
        }


        setActive(
            current.id
        );
    }


    let ticking = false;


    function handleScroll() {
        if (ticking) {
            return;
        }

        window.requestAnimationFrame(
            () => {
                updateActiveSection();

                ticking = false;
            }
        );

        ticking = true;
    }


    window.addEventListener(
        "scroll",
        handleScroll,
        {
            passive: true
        }
    );


    window.addEventListener(
        "resize",
        handleScroll
    );


    updateActiveSection();
});

document
    .querySelectorAll("#reader-content table")
    .forEach((table) => {
        if (table.parentElement.classList.contains("reader-table-wrap")) {
            return;
        }

        const wrapper = document.createElement("div");

        wrapper.classList.add("reader-table-wrap");

        table.parentNode.insertBefore(
            wrapper,
            table
        );

        wrapper.appendChild(
            table
        );
    });