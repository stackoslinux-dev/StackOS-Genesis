#!/usr/bin/env python3

from pathlib import Path
import json
import os
import tempfile


SCHEMA_VERSION = 2
VALID_SOURCES = {
    "auto",
    "manual",
}


def default_config_path():
    xdg = os.environ.get("XDG_CONFIG_HOME")

    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"

    return base / "stackos" / "gpu-manager.json"


class PreferencesError(Exception):
    pass


class PreferencesStore:
    def __init__(self, path=None):
        self.path = (
            Path(path)
            if path is not None
            else default_config_path()
        )

        self.data = {
            "version": SCHEMA_VERSION,
            "applications": {},
        }

    def load(self):
        if not self.path.exists():
            self.data = {
                "version": SCHEMA_VERSION,
                "applications": {},
            }
            return self.data

        try:
            loaded = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as exc:
            raise PreferencesError(
                f"Não foi possível ler {self.path}: {exc}"
            ) from exc

        if not isinstance(loaded, dict):
            raise PreferencesError(
                "Configuração inválida: raiz não é objeto."
            )

        version = loaded.get("version")

        if version not in (1, SCHEMA_VERSION):
            raise PreferencesError(
                "Versão de configuração não suportada."
            )

        applications = loaded.get("applications")

        if not isinstance(applications, dict):
            raise PreferencesError(
                "Configuração inválida: applications."
            )

        migrated = {}

        for desktop_id, value in applications.items():
            if not isinstance(desktop_id, str):
                raise PreferencesError(
                    "Desktop ID inválido."
                )

            if not isinstance(value, dict):
                raise PreferencesError(
                    f"Preferência inválida: {desktop_id}"
                )

            selection = value.get("selection")

            if not isinstance(selection, str):
                raise PreferencesError(
                    f"Seleção inválida: {desktop_id}"
                )

            if version == 1:
                source = "manual"
            else:
                source = value.get("source")

                if source not in VALID_SOURCES:
                    raise PreferencesError(
                        f"Origem inválida: {desktop_id}"
                    )

            migrated[desktop_id] = {
                "selection": selection,
                "source": source,
            }

        self.data = {
            "version": SCHEMA_VERSION,
            "applications": migrated,
        }

        return self.data

    def save(self):
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        payload = json.dumps(
            self.data,
            indent=2,
            ensure_ascii=False
        ) + "\n"

        fd, temporary = tempfile.mkstemp(
            prefix=".gpu-manager-",
            suffix=".tmp",
            dir=self.path.parent
        )

        temporary = Path(temporary)

        try:
            with os.fdopen(
                fd,
                "w",
                encoding="utf-8"
            ) as f:
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())

            os.chmod(
                temporary,
                0o600
            )

            os.replace(
                temporary,
                self.path
            )

        finally:
            if temporary.exists():
                temporary.unlink()

    def set_selection(
        self,
        desktop_id,
        selection,
        source="manual"
    ):
        if not isinstance(desktop_id, str):
            raise PreferencesError(
                "Desktop ID deve ser texto."
            )

        if not desktop_id.endswith(".desktop"):
            raise PreferencesError(
                "Desktop ID deve terminar em .desktop"
            )

        if not isinstance(selection, str):
            raise PreferencesError(
                "Seleção deve ser texto."
            )

        if source not in VALID_SOURCES:
            raise PreferencesError(
                "Origem deve ser auto ou manual."
            )

        self.data["applications"][desktop_id] = {
            "selection": selection,
            "source": source,
        }

    def set_auto_selection(
        self,
        desktop_id,
        selection
    ):
        self.set_selection(
            desktop_id,
            selection,
            source="auto"
        )

    def get_selection(self, desktop_id):
        value = self.data[
            "applications"
        ].get(desktop_id)

        if value is None:
            return None

        return value.get("selection")

    def get_source(self, desktop_id):
        value = self.data[
            "applications"
        ].get(desktop_id)

        if value is None:
            return None

        return value.get("source")

    def get_preference(self, desktop_id):
        value = self.data[
            "applications"
        ].get(desktop_id)

        if value is None:
            return None

        return dict(value)

    def remove_selection(self, desktop_id):
        self.data[
            "applications"
        ].pop(
            desktop_id,
            None
        )


if __name__ == "__main__":
    print(default_config_path())
