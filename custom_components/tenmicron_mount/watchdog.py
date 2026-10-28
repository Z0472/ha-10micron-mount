"""Read-only tracking watchdog based on IsBadStatus()/BadReason() in WatchMount v8.

This module intentionally does not depend on APT, camera sessions or HA helpers.
It evaluates the mount's observed Gstat/GTRK values; offline/connection-loss
notifications are a separate concern because an unpowered parked mount is normal.
"""

NON_ALARM_STATES = {2: "Parking", 3: "Unparking", 4: "Moving home", 5: "Parked"}
ERROR_STATES = {
    1: "STOP key or STOP command",
    7: "Tracking off, mount not moving",
    8: "Motors inhibited / preheating",
    9: "Outside tracking limits",
    11: "Operator intervention required",
    98: "Unknown mount status",
    99: "Mount error status",
}

def evaluate(gstat: int, tracking: bool | None, slew_seconds: float, grace_seconds: int = 60):
    """Return (alarm, reason, watchdog_status) for a responsive mount.

    Matches WatchMount v8 alarm table, independently of expected-tracking switch.
    Normal transitions 2..5 are exempt; Gstat 6 gets a configurable grace.
    Critical GTRK failure in active tracking is an alarm, not a silent pass.
    """
    if gstat in NON_ALARM_STATES:
        state = NON_ALARM_STATES[gstat]
        return False, None, f"Standby – {state}" if gstat == 5 else f"Transition – {state}"
    if gstat == 6:
        if slew_seconds >= grace_seconds:
            reason = f"Slew/dither longer than {grace_seconds} s"
            return True, reason, "ALARM"
        return False, None, "Slew/dither – allowed"
    reason = ERROR_STATES.get(gstat)
    if reason:
        return True, reason, "ALARM"
    if tracking is False:
        return True, f"GTRK=0 while Gstat={gstat}", "ALARM"
    if tracking is None:
        return True, f"Cannot read GTRK while Gstat={gstat}", "ALARM"
    return False, None, "Tracking – monitored" if gstat == 0 else f"Monitoring – Gstat {gstat}"
