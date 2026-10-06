"""Shared Somfy element classification and icon helpers.

Classification is intentionally based only on the Somfy firmware-provided
``label``. User-defined element names are never used, preventing a name in one
language from accidentally matching a device token from another language.
"""

from __future__ import annotations


def _matches(label: str, prefixes: tuple[str, ...]) -> bool:
    return any(label.startswith(prefix) for prefix in prefixes)


def element_icon_family(element: dict) -> str | None:
    """Return the normalized icon family for a Somfy element label."""
    label = (element.get("label") or "").strip().lower()

    # Opening detectors -- specific variants must precede generic openings.
    if _matches(label, ("do vitre", "öm glas", "do cristal", "sa fin.", "od raam", "window od")):
        return "window"
    if _matches(label, ("do gar", "öm gar", "sa gar.", "od garaged", "garage od")):
        return "garage"
    if _matches(label, ("do", "öm", "öffnungsm", "od", "sa")):
        return "door"

    # Motion detectors. Italian SM is deliberately exact/space-delimited so
    # it can never collide with English "Smoke det.".
    if _matches(label, ("dm image", "imagen dm", "dm", "bm", "sm foto", "bd", "be.m.cam", "md cam.", "md")):
        return "motion"
    if label == "sm" or label.startswith("sm "):
        return "motion"

    # Smoke detectors.
    if _matches(label, ("d. fumée", "d. fum", "rauchm", "smoke det.", "rookdet.", "s. fumo", "d. humo")):
        return "smoke"

    # Sirens -- external before internal/general.
    if _matches(label, ("sir ext", "aussensir", "außensir.", "sir. est.", "buitensir.", "outdoor sir")):
        return "siren_external"
    if _matches(label, ("sir int", "innensir", "indoor sir", "binnensir.")):
        return "siren_internal"
    # Some panel variants shorten siren labels. Label-only fallback is safe
    # from custom-name collisions.
    if label.startswith("sir"):
        return "siren_internal"

    # Keypads (LCD and non-LCD share the same icon family).
    if _matches(label, ("cl lcd", "clavier", "lcd-bed", "tastatur", "bedien.", "tecl. lcd", "teclado", "tast. lcd", "tastiera", "lcd-keyp.", "keypad", "lcd keypad")):
        return "keypad"

    # Remote controls.
    if _matches(label, ("tc multi", "tc 4", "multi-fb", "fb", "afst. bed. 4", "m. afst. bed", "multi rc", "rc 4")):
        return "remote"

    # Badges / keys.
    if _matches(label, ("badge", "llave")):
        return "badge"

    # Transmitter / dialer / central unit.
    if _matches(label, ("tr tél", "tr t", "tr. tel.", "übt", "tel. kiezer", "ph dialer")):
        return "central"

    return None


_ICONS = {
    "window": ("mdi:window-closed-variant", "mdi:window-open-variant"),
    "garage": ("mdi:garage-variant", "mdi:garage-open-variant"),
    "door": ("mdi:door-closed", "mdi:door-open"),
    "motion": ("mdi:motion-sensor", "mdi:motion-sensor-off"),
    "smoke": ("mdi:smoke-detector-variant", "mdi:smoke-detector-variant-alert"),
    "siren_external": ("mdi:home-sound-out", "mdi:home-sound-out-outline"),
    "siren_internal": ("mdi:bullhorn", "mdi:bullhorn-outline"),
    "keypad": ("mdi:dialpad", "mdi:keyboard-off-outline"),
    "remote": ("mdi:remote", "mdi:remote-off"),
    "badge": ("mdi:key-variant", "mdi:key-alert"),
    "central": ("mdi:alpha-s-box", "mdi:alpha-s-box-outline"),
}


def get_element_icon(element: dict, alert: bool = False) -> str:
    """Return normal or alert/paused icon for an element."""
    family = element_icon_family(element)
    if family is None:
        return "mdi:alert-rhombus-outline" if alert else "mdi:help-rhombus"
    normal_icon, alert_icon = _ICONS[family]
    return alert_icon if alert else normal_icon
