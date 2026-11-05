import React from 'react';
import { Activity, Cpu, HardDrive, Wifi, BatteryCharging, Battery } from 'lucide-react';

export default function SystemDiagnostics({ telemetry = {} }) {
  const cpu = telemetry.cpu_usage ?? 18.4;
  const mem = telemetry.memory_percent ?? 42.1;
  const memUsed = telemetry.memory_used_gb ?? 6.8;
  const memTotal = telemetry.memory_total_gb ?? 16.0;
  const disk = telemetry.disk_percent ?? 55.0;
  const diskFree = telemetry.disk_free_gb ?? 210.4;
  const up = telemetry.net_upload_kbps ?? 12.4;
  const down = telemetry.net_download_kbps ?? 84.2;
  const battery = telemetry.battery || { percent: 100, power_plugged: true };

  return (
    <div className="relative flex flex-col bg-black/60 border border-cyan-500/30 rounded-xl p-3.5 backdrop-blur-md glow-cyan">
      {/* Header */}
      <div className="flex items-center justify-between pb-2 border-b border-cyan-500/20">
        <div className="flex items-center space-x-2">
          <Activity className="w-4 h-4 text-cyan-400 animate-pulse" />
          <span className="font-orbitron font-bold text-xs tracking-wider text-cyan-200">
            SYSTEM TELEMETRY
          </span>
        </div>
        <div className="flex items-center space-x-1 text-[10px] font-mono-tech text-cyan-400">
          {battery.power_plugged ? (
            <BatteryCharging className="w-3.5 h-3.5 text-emerald-400" />
          ) : (
            <Battery className="w-3.5 h-3.5 text-amber-400" />
          )}
          <span>{battery.percent}%</span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 mt-2.5">
        {/* CPU */}
        <div className="bg-black/40 border border-cyan-500/20 rounded p-2">
          <div className="flex items-center justify-between text-[11px] font-mono-tech text-cyan-400">
            <span className="flex items-center space-x-1">
              <Cpu className="w-3 h-3" />
              <span>CPU LOAD</span>
            </span>
            <span className="font-bold text-cyan-100">{cpu}%</span>
          </div>
          <div className="w-full bg-cyan-950/60 h-1.5 rounded-full overflow-hidden mt-1.5 border border-cyan-500/30">
            <div 
              className="bg-cyan-400 h-full rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, cpu)}%` }}
            />
          </div>
        </div>

        {/* RAM */}
        <div className="bg-black/40 border border-cyan-500/20 rounded p-2">
          <div className="flex items-center justify-between text-[11px] font-mono-tech text-cyan-400">
            <span>RAM {mem}%</span>
            <span className="text-[10px] text-cyan-500">{memUsed}GB</span>
          </div>
          <div className="w-full bg-cyan-950/60 h-1.5 rounded-full overflow-hidden mt-1.5 border border-cyan-500/30">
            <div 
              className="bg-emerald-400 h-full rounded-full transition-all duration-300"
              style={{ width: `${Math.min(100, mem)}%` }}
            />
          </div>
        </div>
      </div>

      {/* Network & Disk */}
      <div className="flex items-center justify-between text-[10px] font-mono-tech text-cyan-500 mt-2.5 pt-2 border-t border-cyan-500/10">
        <div className="flex items-center space-x-1">
          <Wifi className="w-3 h-3 text-cyan-400" />
          <span>NET: ↑{up} KB/s ↓{down} KB/s</span>
        </div>
        <div className="flex items-center space-x-1">
          <HardDrive className="w-3 h-3 text-cyan-400" />
          <span>STORAGE: {diskFree} GB FREE</span>
        </div>
      </div>
    </div>
  );
}

