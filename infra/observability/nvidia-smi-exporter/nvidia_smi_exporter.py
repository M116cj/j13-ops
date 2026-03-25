"""Lightweight GPU exporter using nvidia-smi for consumer GPUs where DCGM is unsupported."""
import subprocess, time
from prometheus_client import Gauge, start_http_server

GPU_UTIL       = Gauge('gpu_utilization_percent', 'GPU utilization percentage')
GPU_MEM_USED   = Gauge('gpu_memory_used_mib', 'GPU memory used in MiB')
GPU_MEM_TOTAL  = Gauge('gpu_memory_total_mib', 'GPU total memory in MiB')
GPU_TEMP       = Gauge('gpu_temperature_celsius', 'GPU temperature in Celsius')
GPU_POWER      = Gauge('gpu_power_draw_watts', 'GPU power draw in Watts')
GPU_FAN        = Gauge('gpu_fan_speed_percent', 'GPU fan speed percentage')

def collect():
    try:
        out = subprocess.check_output([
            'nvidia-smi',
            '--query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw,fan.speed',
            '--format=csv,noheader,nounits'
        ], text=True, timeout=10)
        vals = [v.strip() for v in out.strip().split(',')]
        GPU_UTIL.set(float(vals[0]))
        GPU_MEM_USED.set(float(vals[1]))
        GPU_MEM_TOTAL.set(float(vals[2]))
        GPU_TEMP.set(float(vals[3]))
        GPU_POWER.set(float(vals[4]) if vals[4] != '[N/A]' else 0)
        GPU_FAN.set(float(vals[5]) if vals[5] != '[N/A]' else 0)
    except Exception as e:
        print(f'nvidia-smi collection error: {e}')

if __name__ == '__main__':
    start_http_server(9401)
    print('nvidia-smi-exporter serving on :9401')
    while True:
        collect()
        time.sleep(15)
