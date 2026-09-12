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


# =========================================================
# EXERCISE
# =========================================================

def _wrap_exercise(title, body):
    title = (title or "").strip()
    body = body.strip()

    return (
        "\n"
        "\\begin{quote}\n"
        "\n"
        "MATHERAEXERCISESTART\n"
        "\n"
        "MATHERAEXERCISETITLE\n"
        "\n"
        f"{title}\n"
        "\n"
        "MATHERAEXERCISEBODY\n"
        "\n"
        f"{body}\n"
        "\n"
        "\\end{quote}\n"
    )


def _replace_exercise(match):
    title = match.group(1) or ""
    body = match.group(2)

    return _wrap_exercise(
        title,
        body,
    )


# =========================================================
# EXERCISEBLOCK
# =========================================================

def _replace_exercise_block(match):
    # Ve tvém .sty má exerciseblock implicitně 2 sloupce.
    columns = match.group(1) or "2"

    title = match.group(2)
    body = match.group(3)

    tasks = (
        f"\\begin{{tasks}}({columns})\n"
        f"{body.strip()}\n"
        "\\end{tasks}"
    )

    return _wrap_exercise(
        title,
        tasks,
    )


# =========================================================
# TASKS
# =========================================================

def _replace_tasks(match):
    columns = int(
        match.group(1) or 1
    )

    body = match.group(2)

    tasks = re.split(
        r"\\task\b",
        body,
    )

    tasks = [
        task.strip()
        for task in tasks
        if task.strip()
    ]

    if not tasks:
        return ""

    items = []

    for index, task in enumerate(tasks):
        # Marker uchová informaci o počtu sloupců.
        # mathera.lua jej později odstraní.
        if index == 0:
            task = (
                f"MATHERATASKSCOLS{columns} "
                f"{task}"
            )

        items.append(
            f"\\item {task}"
        )

    return (
        "\n"
        "\\begin{enumerate}\n"
        + "\n".join(items)
        + "\n"
        "\\end{enumerate}\n"
    )


# =========================================================
# HLAVNÍ PREPROCESSING
# =========================================================

def preprocess_tex(source):
    # Pořadí je důležité.
    #
    # exerciseblock nejprve vytvoří explicitní tasks,
    # které následně zpracuje _replace_tasks().

    source = EXERCISE_BLOCK_RE.sub(
        _replace_exercise_block,
        source,
    )

    source = EXERCISE_RE.sub(
        _replace_exercise,
        source,
    )

    source = TASKS_RE.sub(
        _replace_tasks,
        source,
    )

    return source