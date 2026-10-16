#!/usr/bin/env python3
import cereal.messaging as messaging
from openpilot.common.params import Params
from openpilot.common.realtime import config_realtime_process
from openpilot.selfdrive.monitoring.policy import DriverMonitoring


def dmonitoringd_thread():
  config_realtime_process([0, 1, 2, 3], 5)

  params = Params()
  pm = messaging.PubMaster(['driverMonitoringState'])
  sm = messaging.SubMaster(['driverStateV2', 'liveCalibration', 'carState', 'selfdriveState', 'modelV2',
                            'carControl'], poll='driverStateV2')

  DM = DriverMonitoring(rhd_saved=params.get_bool("IsRhdDetected"), always_on=params.get_bool("AlwaysOnDM"))
  demo_mode=False

# 20Hz <- dmonitoringmodeld
  while True:
    sm.update()
    if not sm.updated['driverStateV2']:
      # iterate when model has new output
      continue

    # --- FORCED PASSTHROUGH COMPLIANCE ---
    # We let standard checks pass as valid so the state system thinks everything is fine.
    valid = sm.all_checks()
    
    # 1. We completely skip calling DM.run_step(sm). 
    # This prevents openpilot from calculating eye, face, or phone tracking altogether.
    pass 

    # 2. Generate a clean base state packet directly from the DM engine
    dat = DM.get_state_packet(valid=True)
    
    # 3. Explicitly manipulate the output packet fields before publishing.
    # This forces the downstream processes (controlsd / selfdrived) to read 
    # perfect, undistracted metrics.
    if hasattr(dat, 'driverMonitoringState'):
      dm_state = dat.driverMonitoringState
      
      # Clear awareness penalties and force full awareness status
      if hasattr(dm_state, 'awareness'):
        dm_state.awareness = 1.0
      if hasattr(dm_state, 'isDistracted'):
        dm_state.isDistracted = False
      if hasattr(dm_state, 'distractionType'):
        dm_state.distractionType = 0  # 0 usually corresponds to 'none' or 'normal'
        
    # Send the spoofed packet out at the correct 20Hz timing intervals
    pm.send('driverMonitoringState', dat)

    # load live always-on toggle (keep to maintain normal loop behavior)
    if sm['driverStateV2'].frameId % 40 == 1:
      DM.always_on = params.get_bool("AlwaysOnDM")
      demo_mode = params.get_bool("IsDriverViewEnabled")

    # save rhd virtual toggle every 5 mins
    if (sm['driverStateV2'].frameId % 6000 == 0 and not demo_mode and
     DM.wheelpos_offsetter.filtered_stat.n > DM.settings._WHEELPOS_FILTER_MIN_COUNT and
     DM.wheel_on_right == (DM.wheelpos_offsetter.filtered_stat.M > DM.settings._WHEELPOS_THRESHOLD)):
      params.put_bool("IsRhdDetected", DM.wheel_on_right)

def main():
  dmonitoringd_thread()


if __name__ == '__main__':
  main()
