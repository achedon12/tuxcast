"""``tuxcast doctor``: checks a streaming setup and explains how to fix what is wrong.

A check is a function that takes a :class:`~tuxcast.system.System` and returns findings.
Checks register themselves with :func:`check`, grouped by topic, and only read the system:
running the doctor never changes anything.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from tuxcast.system import System


class Status(enum.Enum):
    OK = "ok"
    INFO = "info"
    WARN = "warn"
    FAIL = "fail"
    SKIP = "skip"


@dataclass(frozen=True)
class Finding:
    status: Status
    summary: str
    detail: str = ""
    fix: str = ""
    action: str = ""  # what the dashboard offers to do about it: "audio", "discord", "deck", "convert"


def ok(summary: str, detail: str = "") -> Finding:
    return Finding(Status.OK, summary, detail)


def info(summary: str, detail: str = "", fix: str = "", action: str = "") -> Finding:
    return Finding(Status.INFO, summary, detail, fix, action)


def warn(summary: str, detail: str = "", fix: str = "", action: str = "") -> Finding:
    return Finding(Status.WARN, summary, detail, fix, action)


def fail(summary: str, detail: str = "", fix: str = "", action: str = "") -> Finding:
    return Finding(Status.FAIL, summary, detail, fix, action)


def skip(summary: str, detail: str = "") -> Finding:
    return Finding(Status.SKIP, summary, detail)


Check = Callable[[System], Iterable[Finding]]


@dataclass(frozen=True)
class Topic:
    key: str
    title: str
    check: Check


TOPICS: list[Topic] = []
TOPIC_ORDER = ["display", "audio", "encoders", "obs", "streamdeck", "discord", "spotify", "network"]


def check(key: str, title: str) -> Callable[[Check], Check]:
    def register(function: Check) -> Check:
        TOPICS.append(Topic(key, title, function))
        return function

    return register


def run(system: System, only: Iterable[str] = ()) -> list[tuple[Topic, list[Finding]]]:
    # importing the modules registers their checks, in this order
    from tuxcast.doctor import (  # noqa: F401
        audio,
        discord,
        display,
        encoders,
        network,
        obs,
        spotify,
        streamdeck,
    )

    wanted = set(only)
    results = []
    for topic in sorted(TOPICS, key=lambda t: TOPIC_ORDER.index(t.key)):
        if wanted and topic.key not in wanted:
            continue
        try:
            findings = list(topic.check(system))
        except Exception as exc:  # a broken probe must not hide the other topics
            findings = [warn("This check crashed", f"{type(exc).__name__}: {exc}",
                             "Please open an issue with the output of `tuxcast doctor --json`.")]
        results.append((topic, findings))
    return results




def as_json(results: list[tuple[Topic, list[Finding]]]) -> list[dict]:
    return [
        {"topic": topic.key, "title": topic.title, "findings": [
            {"status": f.status.value, "summary": f.summary, "detail": f.detail, "fix": f.fix, "action": f.action}
            for f in findings]}
        for topic, findings in results
    ]
