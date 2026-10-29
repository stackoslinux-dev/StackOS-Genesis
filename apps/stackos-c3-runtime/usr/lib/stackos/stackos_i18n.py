#!/usr/bin/env python3

import gettext
import locale
import os
from pathlib import Path


LOCALE_DIR = Path("/usr/share/locale")
DEFAULT_LANGUAGE = "en_US"


def _normalize(value):
    if not value:
        return ""

    value = value.strip()
    value = value.split(".")[0]
    value = value.split("@")[0]

    if value in {"C", "POSIX"}:
        return ""

    return value


def current_language():
    """
    Idioma atual da sessão.

    Prioridade:
      LANGUAGE
      LC_ALL
      LC_MESSAGES
      LANG
      locale Python

    Sem idioma válido -> en_US.
    """

    language = os.environ.get("LANGUAGE", "")

    if language:
        for item in language.split(":"):
            normalized = _normalize(item)
            if normalized:
                return normalized

    for variable in ("LC_ALL", "LC_MESSAGES", "LANG"):
        normalized = _normalize(
            os.environ.get(variable, "")
        )

        if normalized:
            return normalized

    try:
        normalized = _normalize(
            locale.getlocale()[0]
        )

        if normalized:
            return normalized
    except Exception:
        pass

    return DEFAULT_LANGUAGE


def _load_catalog(domain, language):
    """
    Carrega exatamente um catálogo.
    Retorna NullTranslations se ele não existir.
    """

    try:
        return gettext.translation(
            domain,
            localedir=str(LOCALE_DIR),
            languages=[language],
            fallback=False,
        )
    except Exception:
        return gettext.NullTranslations()


class StackOSTranslator:
    """
    Política global StackOS:

      idioma atual
           ↓
      tradução disponível?
        sim -> usa
        não -> procura inglês
           ↓
      inglês é o fallback obrigatório

    A validação da ISO garantirá que o catálogo inglês
    possua todas as strings públicas de cada app.
    """

    def __init__(self, domain):
        self.domain = domain
        self.language = current_language()

        self.primary = _load_catalog(
            domain,
            self.language,
        )

        self.english = _load_catalog(
            domain,
            DEFAULT_LANGUAGE,
        )

    def gettext(self, message):
        # Verifica se o msgid realmente existe no catálogo.
        # Uma tradução válida pode ser idêntica ao texto original.
        primary_catalog = getattr(self.primary, "_catalog", {})

        if message in primary_catalog:
            return self.primary.gettext(message)

        english_catalog = getattr(self.english, "_catalog", {})

        if message in english_catalog:
            return self.english.gettext(message)

        return message


def translator(domain):
    return StackOSTranslator(domain)


def get_translator(domain):
    return StackOSTranslator(domain).gettext
