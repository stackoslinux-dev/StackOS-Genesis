#!/usr/bin/env python3

import argparse
import json

from stackos_gpu_executor import (
    build_execution_plan,
)
from stackos_gpu_preferences import (
    default_config_path,
)


def main():
    parser = argparse.ArgumentParser(
        description=(
            "StackOS GPU Manager - "
            "dry-run de execução por aplicativo"
        )
    )

    parser.add_argument(
        "desktop_id",
        help=(
            "Desktop ID do aplicativo, "
            "por exemplo org.gnome.Calculator.desktop"
        ),
    )

    parser.add_argument(
        "--preferences",
        default=None,
        help=(
            "Arquivo de preferências. "
            "Se omitido, usa o padrão."
        ),
    )

    args = parser.parse_args()

    preferences_path = (
        args.preferences
        or default_config_path()
    )

    plan = build_execution_plan(
        args.desktop_id,
        preferences_path,
    )

    print(
        json.dumps(
            plan,
            indent=2,
            ensure_ascii=False,
            default=str,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
