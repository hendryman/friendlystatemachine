import subprocess
import platform
from pathlib import Path
import time

# Detect the operating system and architecture
if platform.system() == "Windows":
    rclone_path = Path(r"c:\Program Files\rclone\rclone.exe")
elif platform.system() == "Darwin":  # macOS
    if platform.machine() == "arm64":  # Apple Silicon (M1, M2)
        rclone_path = Path("/opt/homebrew/bin/rclone")
    else:  # Intel Macs
        rclone_path = Path("/usr/local/bin/rclone")
else:
    raise EnvironmentError("Unsupported operating system")

drive_path = "/My Drive/friendly_exchange"

local_path = Path("./output")

rclone_config = Path("rclone.conf")

rclone_remote = "silicon-stories"


while True:
    # Ensure all paths are correctly formatted
    copy_up = f'"{rclone_path}" copy "{local_path}" {rclone_remote}:"{drive_path}" --config "{rclone_config}" --progress'
    subprocess.run(copy_up, shell=True)

    copy_down = f'"{rclone_path}" copy {rclone_remote}:"{drive_path}" "{local_path}" --config "{rclone_config}" --progress'
    subprocess.run(copy_down, shell=True)

    time.sleep(60)  # Wait for 60 seconds before syncing again
