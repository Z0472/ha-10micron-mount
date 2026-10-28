"""Human-readable read-only time-check reporting, independent of Home Assistant."""
from datetime import datetime, timezone


def capture_check(result=None, error=None, *, now=None):
    """A snapshot that cannot be overwritten by unrelated mount commands."""
    data = result if isinstance(result, dict) else {}
    when = now or datetime.now(timezone.utc)
    return {
        "status": "error" if error or not data.get("ok") else "ok",
        "at_utc": when.isoformat(),
        "mount_offset_ms": data.get("before_ms"),
        "ntp_system_offset_ms": data.get("ntp_system_offset_ms"),
        "ntp_servers_used": list(data.get("ntp_servers_used") or []),
        "ntp_errors": list(data.get("ntp_errors") or []),
        "proposed_corrections": list(data.get("corrections") or []),
        "error": str(error) if error else None,
    }


def _ms(value, cs=False):
    if value is None:
        return "—"
    number = f"{float(value):+.2f}"
    return number.replace(".", ",") if cs else number


def notification(snapshot, language="en"):
    """Return (title, markdown message); no write commands are issued."""
    cs = str(language).lower().startswith("cs")
    ok = snapshot.get("status") == "ok"
    at_utc = snapshot.get("at_utc") or "—"
    used = ", ".join(snapshot.get("ntp_servers_used") or []) or ("žádný" if cs else "none")
    mount = _ms(snapshot.get("mount_offset_ms"), cs)
    host = _ms(snapshot.get("ntp_system_offset_ms"), cs)
    if cs:
        title = "10Micron – kontrola hodin: " + ("OK" if ok else "CHYBA")
        lines = [
            "**Výsledek:** " + ("Kontrola úspěšná" if ok else "Kontrola selhala"),
            f"**Odchylka hodin montáže vůči NTP:** {mount} ms (kladná = montáž napřed)",
            f"**Korekce NTP vůči hodinám HA:** {host} ms (NTP − HA)",
            f"**Použité NTP servery:** {used}",
            f"**Čas kontroly:** {at_utc}",
            "**Čas montáže nebyl změněn.**",
        ]
        if snapshot.get("proposed_corrections"):
            lines.append("Případná korekce byla pouze navržena, **neprovedena**.")
        if snapshot.get("error"):
            lines.append("**Chyba:** " + str(snapshot["error"]))
    else:
        title = "10Micron – mount clock check: " + ("OK" if ok else "ERROR")
        lines = [
            "**Result:** " + ("Check successful" if ok else "Check failed"),
            f"**Mount offset from NTP:** {mount} ms (positive = mount ahead)",
            f"**NTP offset relative to HA host:** {host} ms (NTP − HA)",
            f"**NTP servers used:** {used}",
            f"**Checked at:** {at_utc}",
            "**The mount clock was not changed.**",
        ]
        if snapshot.get("proposed_corrections"):
            lines.append("A correction was only suggested, **not applied**.")
        if snapshot.get("error"):
            lines.append("**Error:** " + str(snapshot["error"]))
    return title, "\n\n".join(lines)
