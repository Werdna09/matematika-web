import re


TASKS_RE = re.compile(
    r"\\begin\{tasks\}(?:\((\d+)\))?"
    r"(.*?)"
    r"\\end\{tasks\}",
    flags=re.DOTALL,
)


def _replace_tasks(match):
    columns = match.group(1) or "1"
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

    items = "\n".join(
        f"\\item {task}"
        for task in tasks
    )

    return (
        f"\n"
        f"\\begin{{enumerate}}\n"
        f"{items}\n"
        f"\\end{{enumerate}}\n"
    )


def preprocess_tex(source):
    source = TASKS_RE.sub(
        _replace_tasks,
        source,
    )

    return source