"""Optional 10Micron mount clock check/sync using independent NTP sources.

Important: 10Micron :U2# precision is PER TCP CONNECTION. Keep one TCP
session for :U2#, :Gstat#, all :GUDT# samples and any subsequent corrections.
No automatic clock writes are scheduled; normal check sends :U2# to the
private TCP session but never alters the mount's UTC time.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import datetime as dt
import math
import socket
import statistics
import struct
import time

from homeassistant.const import CONF_HOST, CONF_PORT

NTP_EPOCH = 2208988800
FINE_MAX_MS = 999
NO_CORRECTION_MS = 100
ACCEPT_FINAL_MS = 200
FULL_SET_SAFE_STATUSES = {1, 5, 7}


def _ntp_one(host):
    req = bytearray(48)
    req[0] = 0x23
    errs = []
    for family, kind, proto, _, address in socket.getaddrinfo(
        host, 123, type=socket.SOCK_DGRAM
    ):
        try:
            with socket.socket(family, kind, proto) as sock:
                sock.settimeout(2.5)
                sent = time.time()
                sock.sendto(req, address)
                payload, _ = sock.recvfrom(512)
                received = time.time()
            if len(payload) < 48:
                raise ValueError("Short NTP response")
            if (payload[0] >> 6) == 3 or (payload[0] & 7) not in (4, 5):
                raise ValueError("Invalid NTP state")
            if not 1 <= payload[1] <= 15:
                raise ValueError("Invalid NTP stratum")
            data = struct.unpack("!12I", payload[:48])
            if data[10] == 0:
                raise ValueError("Empty NTP timestamp")
            a = data[8] - NTP_EPOCH + data[9] / 2**32
            b = data[10] - NTP_EPOCH + data[11] / 2**32
            offset = ((a - sent) + (b - received)) / 2
            delay = (received - sent) - (b - a)
            if not math.isfinite(offset) or not math.isfinite(delay) or delay > 1.0 or delay < 0:
                raise ValueError("Invalid NTP delay/offset")
            return {"server": host, "offset_s": offset, "rtt_ms": round(delay * 1000, 2)}
        except (OSError, ValueError) as exc:
            errs.append(str(exc))
    raise RuntimeError(f"NTP {host} failed: {' | '.join(errs)}")


def ntp_reference(servers):
    results, errors = [], []
    for host in servers:
        try:
            results.append(_ntp_one(host))
        except (OSError, ValueError, RuntimeError) as exc:
            errors.append(str(exc))
    if not results:
        raise RuntimeError("No valid NTP responses: " + " | ".join(errors))
    offset = statistics.median(x["offset_s"] for x in results)
    if abs(offset) > 300:
        raise RuntimeError("HA system clock differs from NTP by more than 300 seconds")
    return offset, results, errors


def parse_utc(reply):
    """Parse HIGH / ULTRA precision 10Micron UTC; reject coarse clock values.

    The low-precision 'HH:MM.T' response must not be treated as accurate to
    100 milliseconds. It indicates that :U2# was not set on this connection.
    """
    try:
        date, time_str = reply.strip("# ").split(",", 1)
        if "-" in date:
            yr, mo, day = map(int, date.split("-"))
        else:
            mo, day, yr = map(int, date.replace(":", "/").split("/"))
            if yr < 100:
                yr += 2000
        fields = time_str.split(":")
        if len(fields) == 2:
            raise ValueError(
                "Mount returned LOW precision time (HH:MM.T) even after :U2#; "
                f"cannot measure subsecond UTC offset: {reply!r}"
            )
        if len(fields) != 3:
            raise ValueError(f"Invalid UTC time response {reply!r}")
        h, m, seconds = fields
        sec = float(seconds)
        if not math.isfinite(sec) or sec >= 60 or sec < 0:
            raise ValueError("Invalid UTC seconds")
        whole = int(sec)
        fraction = round((sec - whole) * 1_000_000)
        return (
            dt.datetime(yr, mo, day, int(h), int(m), whole, tzinfo=dt.timezone.utc)
            + dt.timedelta(microseconds=fraction)
        ).timestamp()
    except ValueError:
        raise
    except (TypeError, OverflowError) as exc:
        raise ValueError(f"Invalid UTC response {reply!r}") from exc


def format_full_utc(timestamp):
    cs = int(math.floor(timestamp * 100 + 0.5))
    date = dt.datetime.fromtimestamp(cs // 100, dt.timezone.utc)
    return ":SUDT" + date.strftime("%Y-%m-%d,%H:%M:%S") + f".{cs % 100:02d}#"


class MountTimeSession:
    """One private TCP connection, ensuring precision mode applies to reads."""

    def __init__(self, reader, writer, timeout):
        self.reader, self.writer, self.timeout = reader, writer, timeout

    async def send_no_reply(self, command):
        self.writer.write(command.encode("ascii"))
        await asyncio.wait_for(self.writer.drain(), self.timeout)
        # The official 10Micron protocol specifies no ACK for :U2#.
        await asyncio.sleep(0.05)

    async def query(self, command):
        self.writer.write(command.encode("ascii"))
        await asyncio.wait_for(self.writer.drain(), self.timeout)
        raw = await asyncio.wait_for(self.reader.readuntil(b"#"), self.timeout)
        if len(raw) > 128:
            raise ValueError(f"Oversized mount reply to {command}")
        return raw.decode("ascii").rstrip("#").strip()

    async def flag(self, command):
        self.writer.write(command.encode("ascii"))
        await asyncio.wait_for(self.writer.drain(), self.timeout)
        first = await asyncio.wait_for(self.reader.readexactly(1), self.timeout)
        if first not in (b"0", b"1"):
            raise ValueError(f"Invalid flag response {first!r} for {command}")
        try:
            suffix = await asyncio.wait_for(self.reader.read(1), min(self.timeout, 0.25))
        except asyncio.TimeoutError:
            suffix = b""
        if suffix not in (b"", b"#"):
            raise ValueError(f"Unexpected response suffix {suffix!r} for {command}")
        return first.decode("ascii")


@asynccontextmanager
async def open_time_session(config):
    timeout = config.get("timeout", 2)
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(config[CONF_HOST], config[CONF_PORT]), timeout
    )
    try:
        session = MountTimeSession(reader, writer, timeout)
        # Changing this precision is scoped to THIS temporary TCP connection;
        # it never changes the mount clock, pointing, tracking, or other clients.
        await session.send_no_reply(":U2#")
        yield session
    finally:
        writer.close()
        try:
            await asyncio.wait_for(writer.wait_closed(), 1)
        except (OSError, asyncio.TimeoutError):
            pass


async def measure_clock(command, ntp_offset, samples=3):
    readings = []
    for _ in range(samples):
        sent = time.time() + ntp_offset
        reply = await command(":GUDT#")
        received = time.time() + ntp_offset
        try:
            mount_ts = parse_utc(reply)
        except ValueError as exc:
            raise ValueError(f":GUDT# response {reply!r}: {exc}") from exc
        readings.append(
            {"offset_ms": (mount_ts - (sent + received) / 2) * 1000,
             "rtt_ms": (received - sent) * 1000,
             "raw_response": reply}
        )
    return round(statistics.median(x["offset_ms"] for x in readings), 2), readings


async def run(hass, coordinator, dry_run=False):
    cfg = {**coordinator.entry.data, **coordinator.entry.options}
    servers = [s.strip() for s in cfg.get("ntp_servers", "").split(",") if s.strip()]
    if not servers:
        raise ValueError("Configure at least one NTP server")
    ntp_offset, ntp_samples, ntp_errors = await hass.async_add_executor_job(ntp_reference, servers)

    async with open_time_session(cfg) as session:
        code = int(await session.query(":Gstat#"))
        before, readings = await measure_clock(session.query, ntp_offset)
        result = {
            "mode": "dry_run" if dry_run else "sync",
            "ntp_system_offset_ms": round(ntp_offset * 1000, 2),
            "ntp_servers_used": [r["server"] for r in ntp_samples],
            "ntp_errors": ntp_errors,
            "mount_status": code,
            "before_ms": before,
            "raw_utc": [r["raw_response"] for r in readings],
            "corrections": [],
            "after_ms": None,
            "ok": False,
        }

        if abs(before) >= NO_CORRECTION_MS:
            if abs(before) <= FINE_MAX_MS:
                adjustment = int(round(-before))
                cmd = f":NUtim{adjustment:+04d}#"
                if not dry_run:
                    ack = await session.flag(cmd)
                    if ack != "1":
                        raise RuntimeError("Mount rejected fine adjustment")
                result["corrections"].append({"type": "fine", "adjustment_ms": adjustment})
            else:
                if code not in FULL_SET_SAFE_STATUSES:
                    raise RuntimeError("Full UTC correction forbidden while moving/tracking")
                cmd = format_full_utc(time.time() + ntp_offset)
                if not dry_run:
                    ack = await session.flag(cmd)
                    if ack != "1":
                        raise RuntimeError("Mount rejected full UTC set")
                result["corrections"].append({"type": "full_utc"})

        if dry_run:
            result["ok"] = True
            result["note"] = (
                "Read-only clock test; only temporary TCP response precision "
                "was changed with :U2# (per connection)"
            )
            return result

        await asyncio.sleep(0.25)
        after, _ = await measure_clock(session.query, ntp_offset)
        if NO_CORRECTION_MS <= abs(after) <= FINE_MAX_MS:
            adjustment = int(round(-after))
            ack = await session.flag(f":NUtim{adjustment:+04d}#")
            if ack != "1":
                raise RuntimeError("Mount rejected fine residual correction")
            result["corrections"].append({"type": "fine", "adjustment_ms": adjustment})
            await asyncio.sleep(0.25)
            after, _ = await measure_clock(session.query, ntp_offset)
        result["after_ms"] = after
        if abs(after) > ACCEPT_FINAL_MS:
            raise RuntimeError(f"UTC residual exceeds limit: {after} ms")
        result["ok"] = True
        return result
