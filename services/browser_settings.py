"""Browser settings shared by the settings page and the web view."""
import re

from PyQt5 import QtCore

from utils.settings_manager import get_settings_manager


SEARCH_ENGINES = {
    "duckduckgo": ("DuckDuckGo", "https://duckduckgo.com/", "q"),
    "google": ("Google", "https://www.google.com/search", "q"),
    "bing": ("Bing", "https://www.bing.com/search", "q"),
    "yandex": ("Яндекс", "https://yandex.ru/search/", "text"),
}
UA_MODES = {
    "native": "По умолчанию",
    "desktop": "Настольный Chrome",
    "mobile": "Мобильный Chrome (Android)",
    "custom": "Свой User-Agent",
}
STANDARD_PROFILE = {"id": "standard", "name": "Обычный", "persistent": True,
                    "ua_mode": "native", "ua": ""}
GUEST_PROFILE = {"id": "guest", "name": "Приватный", "persistent": False,
                 "ua_mode": "native", "ua": ""}
BUILTIN_PROFILE_IDS = {STANDARD_PROFILE["id"], GUEST_PROFILE["id"]}


def setting(key, default):
    try:
        return get_settings_manager().get_setting(key, default)
    except RuntimeError:
        return default


def search_url(query):
    engine = setting("browser_search_engine", "duckduckgo")
    _, address, param = SEARCH_ENGINES.get(engine if isinstance(engine, str) else "", SEARCH_ENGINES["duckduckgo"])
    url = QtCore.QUrl(address)
    args = QtCore.QUrlQuery()
    args.addQueryItem(param, query)
    url.setQuery(args)
    return url


def profiles():
    values = setting("browser_profiles", [])
    result = [dict(STANDARD_PROFILE), dict(GUEST_PROFILE)]
    ids = set(BUILTIN_PROFILE_IDS)
    if not isinstance(values, list):
        return result
    for value in values[:40]:
        if not isinstance(value, dict):
            continue
        key, name = value.get("id"), value.get("name")
        if not isinstance(key, str) or not re.fullmatch(r"[0-9a-f]{32}", key) or key in ids:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        mode, agent = value.get("ua_mode"), value.get("ua", "")
        if not isinstance(agent, str) or not valid_agent(agent):
            agent = ""
        ids.add(key)
        result.append({"id": key, "name": name.strip()[:48],
                       "persistent": value.get("persistent") is True,
                       "ua_mode": mode if isinstance(mode, str) and mode in UA_MODES else "native",
                       "ua": agent})
    return result


def default_profile():
    key = setting("browser_default_profile", "standard")
    return next((profile for profile in profiles() if profile["id"] == key), dict(STANDARD_PROFILE))


def valid_agent(text):
    return len(text) <= 512 and all(32 <= ord(char) <= 126 for char in text)


def user_agent(profile, native):
    mode = profile["ua_mode"]
    if mode == "custom":
        return profile["ua"] or native
    chrome = re.search(r"Chrome/[0-9.]+", native)
    if not chrome or mode == "native":
        return native
    if mode == "mobile":
        platform, mobile = "Linux; Android 11", " Mobile"
    else:
        platform, mobile = "Windows NT 10.0; Win64; x64", ""
    return (f"Mozilla/5.0 ({platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"{chrome[0]}{mobile} Safari/537.36")
