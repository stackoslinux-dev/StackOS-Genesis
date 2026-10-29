#!/usr/bin/env python3

from stackos_gpu_backend import discover_applications
from stackos_gpu_policy import choose_selection
from stackos_gpu_preferences import PreferencesStore
from stackos_gpu_resolver import (
    resolve_selection,
    switcheroo_devices,
)


class RunPlanError(Exception):
    pass


def find_application(desktop_id):
    for app in discover_applications():
        if app["desktop_id"] == desktop_id:
            return app

    return None


def resolve_auto_selection(app):
    selection = choose_selection(
        app,
        user_selection=None
    )

    gpu_id = resolve_selection(
        selection
    )

    if gpu_id is not None:
        return selection, gpu_id

    # Se o automático pediu GPU discreta e ela não
    # está disponível, usamos a GPU padrão.
    if selection != "role:default":
        selection = "role:default"

        gpu_id = resolve_selection(
            selection
        )

    return selection, gpu_id


def build_run_plan(
    desktop_id,
    preferences_path=None
):
    app = find_application(desktop_id)

    if app is None:
        raise RunPlanError(
            f"Aplicativo não encontrado: {desktop_id}"
        )

    preferences = PreferencesStore(
        preferences_path
    )

    preferences.load()

    preference = preferences.get_preference(
        desktop_id
    )

    selection = None
    source = None
    gpu_id = None

    devices = switcheroo_devices()
    multiple_gpus = len(devices) > 1

    if preference is not None:
        selection = preference["selection"]
        source = preference["source"]

        gpu_id = resolve_selection(
            selection
        )

        if gpu_id is None:
            if source == "manual":
                raise RunPlanError(
                    "A GPU escolhida pelo usuário "
                    "não está disponível: "
                    f"{selection}"
                )

            selection, gpu_id = resolve_auto_selection(
                app
            )

            preferences.set_auto_selection(
                desktop_id,
                selection
            )
            preferences.save()

    else:
        selection, gpu_id = resolve_auto_selection(
            app
        )

        preferences.set_auto_selection(
            desktop_id,
            selection
        )
        preferences.save()

        source = "auto"

    if source is None:
        source = preferences.get_source(
            desktop_id
        )

    # Em sistema de uma GPU não precisamos envolver
    # switcherooctl em cada abertura.
    uses_gpu_override = (
        multiple_gpus
        and gpu_id is not None
    )

    return {
        "desktop_id": app["desktop_id"],
        "name": app["name"],
        "exec": app["exec"],
        "desktop_file": app["path"],
        "selection": selection,
        "selection_source": source,
        "switcheroo_gpu_id": (
            gpu_id
            if uses_gpu_override
            else None
        ),
        "uses_gpu_override": uses_gpu_override,
    }
