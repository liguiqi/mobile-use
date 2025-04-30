import subprocess
import time
ckpt_dir_prefix = r"xxx\android_world\runs"
def kill_emulator():
    command = 'for /f "tokens=2" %i in (\'tasklist ^| findstr "qemu-system-x86_64"\') do taskkill /PID %i /F'
    subprocess.run(command, shell=True)

for _ in range(5):
    print("Starting emulator")
    process = subprocess.Popen(r"adb -P 5038 start-server && set ANDROID_ADB_SERVER_PORT=5038 && ...\emulator -avd AndroidWorldAvd -no-snapshot -grpc 8554", shell=True)
    print("Emulator started")
    time.sleep(120)
    print("Running script")
    name="xxx"
    subprocess.run(rf"python -u run.py --checkpoint_dir={ckpt_dir_prefix}\name --mobileuse_agent_name=MultiAgent >> logs\name.log 2>&1", shell=True)
    print("Script ran")
    print("Force Killing emulator")
    kill_emulator()
    print("Emulator force killed")
    time.sleep(20)
