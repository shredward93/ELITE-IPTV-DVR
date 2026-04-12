#pragma once

#include <string>
#include <vector>

#include <kodi/addon-instance/PVR.h>

namespace eliteiptv
{
class Settings
{
public:
  std::string server_ip = "192.168.1.100";
  int server_port = 8080;
  bool auto_dvr = false;
  std::string default_mode = "live";
};

class Client : public kodi::addon::CInstancePVRClient
{
public:
  explicit Client(KODI_HANDLE instance);
  ~Client() override = default;

  PVR_ERROR GetCapabilities(kodi::addon::PVRCapabilities& capabilities) override;
  PVR_ERROR GetBackendName(std::string& name) override;
  PVR_ERROR GetBackendVersion(std::string& version) override;
  PVR_ERROR GetBackendHostname(std::string& hostname) override;
  PVR_ERROR GetConnectionString(std::string& connectionString) override;
  PVR_ERROR GetDriveSpace(long long& total, long long& used) override;
  PVR_ERROR GetChannelsAmount(int& amount) override;
  PVR_ERROR GetChannels(bool radio, kodi::addon::PVRChannelsResultSet& results) override;
  PVR_ERROR GetChannelStreamProperties(const kodi::addon::PVRChannel& channel, std::vector<kodi::addon::PVRStreamProperty>& properties) override;
  PVR_ERROR GetEPGForChannel(int channelUid, time_t start, time_t end, kodi::addon::PVREPGTagsResultSet& results) override;
  PVR_ERROR GetRecordingsAmount(bool deleted, int& amount) override;
  PVR_ERROR GetRecordings(bool deleted, kodi::addon::PVRRecordingsResultSet& results) override;
  PVR_ERROR GetTimersAmount(int& amount) override;
  PVR_ERROR GetTimers(kodi::addon::PVRTimersResultSet& results) override;
  PVR_ERROR AddTimer(const kodi::addon::PVRTimer& timer) override;
  PVR_ERROR DeleteTimer(const kodi::addon::PVRTimer& timer) override;
  PVR_ERROR UpdateTimer(const kodi::addon::PVRTimer& timer) override;
  PVR_ERROR OpenLiveStream(const kodi::addon::PVRChannel& channel) override;
  void CloseLiveStream() override;

private:
  Settings m_settings;
  std::string BuildBaseUrl() const;
  std::string BuildLiveUrl(unsigned int channelId) const;
  std::string BuildDvrUrl() const;
  std::string BuildScheduleUrl() const;
};
} // namespace eliteiptv
