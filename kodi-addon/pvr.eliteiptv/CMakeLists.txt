cmake_minimum_required(VERSION 3.16)
project(pvr.eliteiptv)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# This project is intended to be built inside the Kodi add-on build system.
# See Kodi's PVR demo client for the official build flow.

add_library(pvr.eliteiptv MODULE
    src/addon.cpp
    src/client.cpp
)

target_include_directories(pvr.eliteiptv PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
)

# Kodi's add-on toolchain provides the correct PVR headers and link settings.
# When building inside Kodi's add-on build tree, this module will be packaged
# as the native PVR client binary.
