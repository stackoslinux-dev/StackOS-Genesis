#!/usr/bin/env python3

import shlex


class DesktopExecError(Exception):
    pass


REMOVE_CODES = {
    "%f",
    "%F",
    "%u",
    "%U",
    "%d",
    "%D",
    "%n",
    "%N",
    "%v",
    "%m",
}


def expand_exec(
    exec_line,
    *,
    app_name=None,
    desktop_file=None,
    icon=None,
):
    if not isinstance(exec_line, str):
        raise DesktopExecError(
            "Exec deve ser texto."
        )

    if not exec_line.strip():
        raise DesktopExecError(
            "Exec vazio."
        )

    try:
        tokens = shlex.split(
            exec_line,
            posix=True
        )
    except ValueError as exc:
        raise DesktopExecError(
            f"Exec inválido: {exc}"
        ) from exc

    result = []

    for token in tokens:
        if token in REMOVE_CODES:
            continue

        if token == "%c":
            if app_name:
                result.append(app_name)
            continue

        if token == "%k":
            if desktop_file:
                result.append(desktop_file)
            continue

        if token == "%i":
            if icon:
                result.extend([
                    "--icon",
                    icon,
                ])
            continue

        if token == "%%":
            result.append("%")
            continue

        cleaned = token

        for code in REMOVE_CODES:
            cleaned = cleaned.replace(
                code,
                ""
            )

        cleaned = cleaned.replace(
            "%%",
            "%"
        )

        if "%c" in cleaned:
            cleaned = cleaned.replace(
                "%c",
                app_name or ""
            )

        if "%k" in cleaned:
            cleaned = cleaned.replace(
                "%k",
                desktop_file or ""
            )

        if "%i" in cleaned:
            raise DesktopExecError(
                "%i embutido em argumento "
                "não é suportado."
            )

        if "%" in cleaned:
            raise DesktopExecError(
                f"Código Exec desconhecido: {cleaned}"
            )

        if cleaned:
            result.append(cleaned)

    if not result:
        raise DesktopExecError(
            "Exec não gerou comando."
        )

    return result


if __name__ == "__main__":
    print(
        expand_exec(
            "firefox %u",
            app_name="Firefox",
            desktop_file=(
                "/usr/share/applications/"
                "firefox.desktop"
            ),
        )
    )
