#!/usr/bin/env python3

import json

from stackos_gpu_backend import system_state
from stackos_gpu_preferences import PreferencesStore


def build_state(preferences_path=None):
    system = system_state()

    preferences = PreferencesStore(
        preferences_path
    )

    preferences.load()

    for app in system["applications"]:
        app["gpu_selection"] = (
            preferences.get_selection(
                app["desktop_id"]
            )
        )

    system["preferences"] = preferences.data

    return system


if __name__ == "__main__":
    print(
        json.dumps(
            build_state(),
            indent=2,
            ensure_ascii=False
        )
    )
