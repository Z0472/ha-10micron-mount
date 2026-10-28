"""Simulated 10Micron TCP session. No hardware/network required."""
import asyncio
import importlib.util
import sys
import types
import unittest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

# Avoid requiring HA in standalone protocol tests.
ha = types.ModuleType('homeassistant')
hac = types.ModuleType('homeassistant.const')
hac.CONF_HOST = 'host'
hac.CONF_PORT = 'port'
sys.modules.setdefault('homeassistant', ha)
sys.modules.setdefault('homeassistant.const', hac)
file = Path(__file__).resolve().parents[1] / 'custom_components/tenmicron_mount/time_sync.py'
spec = importlib.util.spec_from_file_location('tenmicron_time_precision', file)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

class MockHass:
    async def async_add_executor_job(self, func, *args):
        return (0.0, [{'server': 'simulated'}], [])

class MockCoordinator:
    def __init__(self, port):
        self.entry = types.SimpleNamespace(data={'host': '127.0.0.1', 'port': port, 'timeout': 1.5, 'ntp_servers': 'simulated'}, options={})

class TimeProtocol(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.connections = []
        self.status = 5
        self.offset_seconds = 0
        self.server = await asyncio.start_server(self.server_handler, '127.0.0.1', 0)
        self.port = self.server.sockets[0].getsockname()[1]
    async def asyncTearDown(self):
        self.server.close()
        await self.server.wait_closed()

    async def server_handler(self, reader, writer):
        commands = []
        self.connections.append(commands)
        precision = False
        try:
            while True:
                raw = await reader.readuntil(b'#')
                cmd = raw.decode('ascii')
                commands.append(cmd)
                if cmd == ':U2#':
                    precision = True
                elif cmd == ':Gstat#':
                    writer.write(f'{self.status}#'.encode('ascii'))
                    await writer.drain()
                elif cmd == ':GUDT#':
                    utc = datetime.now(timezone.utc) + timedelta(seconds=self.offset_seconds)
                    data = utc.strftime('%Y-%m-%d,%H:%M:%S.') + f'{utc.microsecond // 10000:02d}' if precision else utc.strftime('%m/%d/%y,%H:%M.0')
                    writer.write((data+'#').encode('ascii'))
                    await writer.drain()
                else:
                    writer.write(b'1')
                    await writer.drain()
        except (asyncio.IncompleteReadError,ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_check_stays_on_one_session_and_is_read_only(self):
        result = await mod.run(MockHass(), MockCoordinator(self.port), dry_run=True)
        self.assertTrue(result['ok'])
        self.assertEqual(result['mode'], 'dry_run')
        self.assertEqual(len(self.connections), 1)
        self.assertEqual(self.connections[0], [':U2#',':Gstat#',':GUDT#',':GUDT#',':GUDT#'])
        self.assertEqual(len(result['raw_utc']), 3)
        self.assertTrue(all(x.count(':')==2 for x in result['raw_utc']))

    async def test_large_time_change_blocked_during_tracking(self):
        self.status = 0  # TRACKING, unsafe for full time set
        self.offset_seconds = 5
        with self.assertRaisesRegex(RuntimeError, 'forbidden'):
            await mod.run(MockHass(), MockCoordinator(self.port), dry_run=False)
        commands = [c for session in self.connections for c in session]
        self.assertIn(':U2#', commands)
        self.assertFalse(any(c.startswith(':SUDT') or c.startswith(':NUtim') for c in commands))

    async def test_low_precision_is_rejected_for_subsecond_check(self):
        with self.assertRaisesRegex(ValueError, 'LOW precision'):
            mod.parse_utc('10/10/26,14:03.4')

    async def test_high_precision_format_and_previous_date_modes(self):
        self.assertEqual(mod.parse_utc('2026-10-10,12:03:04.56'), datetime(2026,10,10,12,3,4,560000,tzinfo=timezone.utc).timestamp())
        self.assertEqual(mod.parse_utc('10:10:26,12:03:04.5'), datetime(2026,10,10,12,3,4,500000,tzinfo=timezone.utc).timestamp())

if __name__=='__main__': unittest.main()
