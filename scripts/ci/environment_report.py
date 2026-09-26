"""Report installed distribution metadata without importing runtime backends."""
from __future__ import annotations

from html import escape
from importlib.metadata import distributions
import os
import platform
from pathlib import Path


def cell(value: str) -> str:
    return escape(value).replace('|', '&#124;').replace('\r', ' ').replace('\n', ' ')


def render(python: str, system: str, packages: list[tuple[str, str]]) -> str:
    lines = [
        '## Offline verification environment', '',
        f'Python: {cell(python)}; OS: {cell(system)}.', '',
        'Installed distributions after test-extra installation; not a lockfile,',
        'dependency security audit, or statement that every installed package was exercised.',
        'See job steps for test results. Optional camera/serial backends, models,',
        'native helpers and physical execution are not qualified by this matrix.', '',
        '| Distribution | Version |', '| --- | --- |',
    ]
    lines.extend(f'| {cell(name)} | {cell(version)} |'
                 for name, version in sorted(packages, key=lambda item: item[0].casefold()))
    return '\n'.join(lines) + '\n'


def main() -> None:
    report = render(platform.python_version(), platform.system(), [
        (dist.metadata.get('Name', '(unnamed)'), dist.version)
        for dist in distributions()
    ])
    print(report, end='')
    # Only GitHub's designated summary file is written, when supplied by the runner.
    # Do not dump environment variables, pip configuration, install URLs or paths.
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary:
        with Path(summary).open('a', encoding='utf-8') as stream:
            stream.write(report)


if __name__ == '__main__':
    main()
