#!/usr/bin/env python3

import subprocess

from stackos_desktop_exec import expand_exec
from stackos_gpu_launcher import build_launch_command
from stackos_gpu_runplan import build_run_plan


class ExecutorError(Exception):
    pass


def build_execution_plan(
    desktop_id,
    preferences_path=None
):
    plan = build_run_plan(
        desktop_id,
        preferences_path
    )

    command = expand_exec(
        plan["exec"],
        app_name=plan["name"],
        desktop_file=plan["desktop_file"],
    )

    if plan["uses_gpu_override"]:
        final_command = build_launch_command(
            plan["switcheroo_gpu_id"],
            command
        )
    else:
        final_command = command

    return {
        **plan,
        "command": command,
        "final_command": final_command,
    }


def execute_plan(
    plan,
    *,
    check=False
):
    if not isinstance(plan, dict):
        raise ExecutorError(
            "Plano de execução inválido."
        )

    command = plan.get("final_command")

    if not isinstance(command, list):
        raise ExecutorError(
            "final_command inválido."
        )

    if not command:
        raise ExecutorError(
            "final_command vazio."
        )

    if not all(
        isinstance(item, str)
        for item in command
    ):
        raise ExecutorError(
            "Argumentos do comando inválidos."
        )

    try:
        return subprocess.run(
            command,
            check=check
        )
    except OSError as exc:
        raise ExecutorError(
            f"Falha ao executar: {exc}"
        ) from exc



def launch_plan(
    plan,
):
    if not isinstance(plan, dict):
        raise ExecutorError(
            "Plano de execução inválido."
        )

    command = plan.get("final_command")

    if not isinstance(command, list):
        raise ExecutorError(
            "final_command inválido."
        )

    if not command:
        raise ExecutorError(
            "final_command vazio."
        )

    if not all(
        isinstance(item, str)
        for item in command
    ):
        raise ExecutorError(
            "Argumentos do comando inválidos."
        )

    try:
        return subprocess.Popen(
            command
        )
    except OSError as exc:
        raise ExecutorError(
            f"Falha ao executar: {exc}"
        ) from exc

def execute_application(
    desktop_id,
    preferences_path=None,
    *,
    check=False
):
    plan = build_execution_plan(
        desktop_id,
        preferences_path
    )

    return execute_plan(
        plan,
        check=check
    )


if __name__ == "__main__":
    raise SystemExit(
        "Use este módulo através da aplicação."
    )
