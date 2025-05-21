import subprocess
import time
import argparse
import os

parser = argparse.ArgumentParser(description="Run Android emulator and execute script.")
parser.add_argument("--checkpoint_dir", type=str, default="~/android_world/runs/ckpt", help="Path to the checkpoint directory.")
parser.add_argument("--output_path", type=str, default="./output.log", help="Path to the output file.")
parser.add_argument("--max_step", type=str, default="15", help="Path to the output file.")
parser.add_argument("--n_task_combinations", type=int, default=5, help="Name of the emulator to run.")

args = parser.parse_args()
ckpt_dir = args.checkpoint_dir
output_path = args.output_path
max_step = args.max_step
n_task_combinations = args.n_task_combinations

# def kill_emulator():
#     command = 'pkill -f "qemu-system-x86_64"'
#     subprocess.run(command, shell=True)
#     command = 'pkill -f "emulator"'
#     subprocess.run(command, shell=True)

for _ in range(100):
    os.environ["ANDROID_MAX_STEP"] = max_step
    # print("Starting emulator")
    # process = subprocess.Popen("adb start-server && ~/Library/Android/sdk/emulator/emulator -avd AndroidWorldAvd -no-window -no-audio -no-snapshot -grpc 8554", shell=True)
    # print("Emulator started")
    # time.sleep(120)
    print("Running script")
    subprocess.run(f"python -u run.py --checkpoint_dir={ckpt_dir} --n_task_combinations={n_task_combinations} >> {output_path} 2>&1", shell=True)
    print("Script ran")
    # print("Force Killing emulator")
    # kill_emulator()
    # print("Emulator force killed")
    time.sleep(20)
