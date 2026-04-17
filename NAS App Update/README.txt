========================================
  ELITE IPTV DVR - NAS Update Shortcuts
========================================

QUICK START (Normal Code Changes):
1. Double-click "1 - Push to GitHub.bat"
2. Double-click "2 - Update NAS.bat"
   Done! Your changes are live.

----------------------------------------
WHEN DO I NEED A REBUILD?
----------------------------------------

USE "2 - Update NAS.bat" (Fast - 10 seconds):
  server_headless.py changes
  core/*.py changes
  static/* files
  Most day-to-day development

USE "3 - Full Rebuild NAS.bat" (Slow - 2-5 minutes):
  requirements.txt changed (added/updated Python packages)
  Dockerfile changed
  Need to update base image for security patches

----------------------------------------
HOW TO TELL IF REBUILD IS NEEDED
----------------------------------------

Check the file you modified:
  Python files (.py)  ->  Restart only
  requirements.txt    ->  REBUILD REQUIRED
  Dockerfile          ->  REBUILD REQUIRED

The volume mounts in docker-compose.yml make most
updates instant. Only dependency changes need a rebuild.

----------------------------------------
FIRST TIME SETUP
----------------------------------------

1. Edit "2 - Update NAS.bat" and "3 - Full Rebuild NAS.bat"
2. Change these lines at the top:
   set NAS_IP=192.168.1.100     <- Your NAS IP
   set NAS_USER=admin            <- Your NAS username
   set NAS_PATH=/volume1/docker/elite-iptv-dvr  <- Your project path

3. Ensure SSH is enabled on your Synology NAS:
   Control Panel -> Terminal & SNMP -> Enable SSH

4. Run this once in Command Prompt to save the host key:
   ssh your-user@your-nas-ip
   (type "yes" when asked)

----------------------------------------
WHAT IS A REBUILD VS RESTART?
----------------------------------------

RESTART ("2 - Update NAS.bat"):
  - Stops container, starts it again
  - New code is loaded from volume mounts
  - Takes ~10 seconds
  - Requirements.txt changes are NOT picked up

REBUILD ("3 - Full Rebuild NAS.bat"):
  - Rebuilds the entire Docker image from Dockerfile
  - Reinstalls all Python packages from requirements.txt
  - Takes 2-5 minutes depending on NAS speed
  - Needed for dependency changes

----------------------------------------
TROUBLESHOOTING
----------------------------------------

"Connection refused":
  - SSH not enabled on NAS
  - Wrong IP address

"Permission denied":
  - Wrong username
  - Need to set up SSH key or use password

"docker-compose: command not found":
  - Run via Synology Container Manager instead
  - Or use: sudo docker-compose

----------------------------------------
