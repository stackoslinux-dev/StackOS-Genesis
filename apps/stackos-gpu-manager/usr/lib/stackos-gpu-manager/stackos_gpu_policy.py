#!/usr/bin/env python3


class PolicyError(Exception):
    pass


def choose_selection(app, user_selection=None):
    """
    Decide qual seleção de GPU usar.

    Prioridade:
    1. escolha manual do usuário;
    2. PrefersNonDefaultGPU=true;
    3. GPU padrão.
    """

    if not isinstance(app, dict):
        raise PolicyError("Aplicativo inválido.")

    if user_selection is not None:
        return user_selection

    if app.get("prefers_non_default_gpu") is True:
        return "role:discrete"

    return "role:default"


if __name__ == "__main__":
    raise SystemExit(
        "Use este módulo através da aplicação."
    )
