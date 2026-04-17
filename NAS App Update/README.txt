========================================
  ELITE IPTV DVR - NAS Update Shortcuts
========================================

WORKFLOW (Using Git Server app on NAS):

1. Push changes to GitHub:
   Double-click "1 - Push to GitHub.bat"

2. On your NAS (via DSM or Git Server app):
   - Pull the latest code from GitHub
   - Restart the Docker container in Container Manager
   
   Done! Your changes are live.

----------------------------------------
WHEN DO I NEED A REBUILD?
----------------------------------------

CODE CHANGES (Fast - Just restart container):
  server_headless.py changes
  core/*.py changes
  static/* files
  Most day-to-day development

REBUILD REQUIRED (Slow - 2-5 minutes):
  requirements.txt changed (new Python packages)
  Dockerfile changed
  Need to update base image for security patches

  To rebuild: In Container Manager, stop the container,
  then "Action" -> "Rebuild" -> "Reset and rebuild"

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
