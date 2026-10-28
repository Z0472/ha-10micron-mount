"""Optional, explicitly invoked 10Micron refraction controls from HA sensors.

Reuses limits/protocol from gm3000_update_refraction.py. No CHMI fetching:
pressure is supplied by the HA pressure entity configured by the user.
"""
from __future__ import annotations
from datetime import datetime,timezone
import math


def valid_reading(hass,entity_id,kind):
    if not entity_id: raise ValueError(f'{kind} HA sensor is not configured')
    state=hass.states.get(entity_id)
    if state is None or state.state in ('unknown','unavailable','none',''):
        raise ValueError(f'{kind} HA sensor unavailable: {entity_id}')
    age=(datetime.now(timezone.utc)-state.last_updated).total_seconds()
    limit=180*60 if kind=='pressure' else 60*60
    if age>limit: raise ValueError(f'{kind} reading is stale ({age/60:.1f} min)')
    value=float(state.state.replace(',','.'))
    if not math.isfinite(value): raise ValueError(f'Invalid {kind} reading')
    unit=state.attributes.get('unit_of_measurement','')
    if kind=='pressure':
        if unit in ('Pa',): value/=100
        elif unit not in ('hPa','mbar',''): raise ValueError('Pressure sensor must provide hPa/mbar/Pa')
        if not 850<=value<=1050: raise ValueError(f'Pressure out of range: {value} hPa')
    else:
        if unit in ('°F','F'): value=(value-32)*5/9
        elif unit not in ('°C','C',''): raise ValueError('Temperature sensor must provide °C/°F')
        if not -40<=value<=50: raise ValueError(f'Temperature out of range: {value} C')
    return round(value,1)

async def run(hass,coordinator,mode,dry_run=False):
    cfg={**coordinator.entry.data,**coordinator.entry.options}
    if mode=='disable': commands=[':SREF0#',':GREF#']
    else:
        pressure=valid_reading(hass,cfg.get('pressure_entity',''),'pressure')
        temp=valid_reading(hass,cfg.get('temperature_entity',''),'temperature')
        commands=[f':SRPRS{pressure:06.1f}#',f':SRTMP{temp:+06.1f}#']
        if mode=='enable': commands+=[':SREF1#']
        commands+=[':GRPRS#',':GRTMP#',':GREF#']
    result={'mode':mode,'dry_run':dry_run,'commands':commands,'ok':False}
    if mode!='disable': result.update(pressure_hpa=pressure,temperature_c=temp)
    if dry_run:
        result['ok']=True
        return result
    responses=[]
    for cmd in commands:
        if cmd.startswith((':SREF',':SRPRS',':SRTMP')):
            reply=await coordinator.mount_flag(cmd)
            if reply!='1': raise RuntimeError(f'Mount rejected command {cmd}: {reply}')
        elif cmd==':GREF#': reply=await coordinator.mount_flag(cmd)
        else: reply=await coordinator.mount_query(cmd)
        responses.append({'command':cmd,'reply':reply})
    result['responses']=responses
    if mode!='disable':
        got_pressure=float(next(x['reply'] for x in responses if x['command']==':GRPRS#'))
        got_temp=float(next(x['reply'] for x in responses if x['command']==':GRTMP#'))
        if abs(got_pressure-pressure)>.2 or abs(got_temp-temp)>.2:
            raise RuntimeError('Refraction readback mismatch')
    got_refraction=next(x['reply'] for x in responses if x['command']==':GREF#')
    if mode=='enable' and got_refraction!='1': raise RuntimeError('Refraction did not enable')
    if mode=='disable' and got_refraction!='0': raise RuntimeError('Refraction did not disable')
    result['ok']=True
    result['refraction_enabled']=(got_refraction=='1')
    return result
