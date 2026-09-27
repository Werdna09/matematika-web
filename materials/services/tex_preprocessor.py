import re


# =========================================================
# REGEXY
# =========================================================

EXERCISE_BLOCK_RE = re.compile(
    r"\\begin\{exerciseblock\}"
    r"(?:\[(\d+)\])?"
    r"\{([^{}]*)\}"
    r"(.*?)"
    r"\\end\{exerciseblock\}",
    flags=re.DOTALL,
)


EXERCISE_RE = re.compile(
    r"\\begin\{exercise\}"
    r"(?:\[([^\]]*)\])?"
    r"(.*?)"
    r"\\end\{exercise\}",
    flags=re.DOTALL,
)


TASKS_RE = re.compile(
    r"\\begin\{tasks\}"
    r"(?:\((\d+)\))?"
    r"(.*?)"
    r"\\end\{tasks\}",
    flags=re.DOTALL,
)


IMPORTANT_RE = re.compile(
    r"\\important\{([^{}]*)\}"
)


NEWCOLUMN_RE = re.compile(
    r"(?m)^[ \t]*\\newcolumntype[^\n]*(?:\n|$)"
)


ROWCOLOR_RE = re.compile(
    r"\\rowcolor\s*\{[^{}]*\}\s*"
)


CUSTOM_CENTER_COLUMN_RE = re.compile(
    r"C\s*\{[^{}]*\}"
)


# =========================================================
# TABULKY
# =========================================================

def _normalize_tables(source):
    """
    Pandoc neumí vlastní sloupcový typ C{...} používaný v tabular.

    Pro web proto:
    - C{4.7cm} -> c
    - odstraníme \\rowcolor{...}

    PDF zdroj se nemění; jde pouze o preprocessing pro web.
    """

    source = CUSTOM_CENTER_COLUMN_RE.sub(
        "c",
        source,
    )

    source = ROWCOLOR_RE.sub(
        "",
        source,
    )

    return source


# =========================================================
# BOXY
# =========================================================

BOX_ENVIRONMENTS = {
    "definitionbox": "definition",
    "examplebox": "example",
    "notebox": "note",
    "historicalbox": "historical",
    "solutionbox": "solution",
}


