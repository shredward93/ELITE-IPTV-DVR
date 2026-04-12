#include "client.h"

#include <ctime>
#include <sstream>

namespace eliteiptv
{
Client::Client(KODI_HANDLE instance)
  : kodi::addon::CInstancePVRClient(instance)
{
}

PVR_ERROR Client::GetCapabilities(kodi::addon::PVRCapabilities& capabilities)
{
  capabilities.SetSupportsTV(true);
  capabilities.SetSupportsRadio(false);
  capabilities.SetSupportsEPG(true);
  capabilities.SetSupportsRecordings(true);
  capabilities.SetSupportsTimers(true);
  capabilities.SetSupportsChannelGroups(true);
  capabilities.SetSupportsInputStream(true);
  capabilities.SetHandlesInputStream(true);
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetBackendName(std::string& name)
{
  name = "ELITE IPTV DVR";
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetBackendVersion(std::string& version)
{
  version = "2.0.0";
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetBackendHostname(std::string& hostname)
{
  hostname = m_settings.server_ip;
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetConnectionString(std::string& connectionString)
{
  connectionString = BuildBaseUrl();
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetDriveSpace(long long& total, long long& used)
{
  total = 0;
  used = 0;
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetChannelsAmount(int& amount)
{
  amount = 0;
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetChannels(bool radio, kodi::addon::PVRChannelsResultSet& results)
{
  (void)radio;
  (void)results;
  return PVR_ERROR_NOT_IMPLEMENTED;
}

PVR_ERROR Client::GetChannelStreamProperties(const kodi::addon::PVRChannel& channel, std::vector<kodi::addon::PVRStreamProperty>& properties)
{
  properties.clear();
  properties.emplace_back("inputstream", "inputstream.ffmpegdirect");
  properties.emplace_back("inputstream.adaptive.manifest_type", "hls");
  properties.emplace_back("streamurl", BuildLiveUrl(channel.GetUniqueId()));
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetEPGForChannel(int channelUid, time_t start, time_t end, kodi::addon::PVREPGTagsResultSet& results)
{
  (void)channelUid;
  (void)start;
  (void)end;
  (void)results;
  return PVR_ERROR_NOT_IMPLEMENTED;
}

PVR_ERROR Client::GetRecordingsAmount(bool deleted, int& amount)
{
  (void)deleted;
  amount = 0;
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetRecordings(bool deleted, kodi::addon::PVRRecordingsResultSet& results)
{
  (void)deleted;
  (void)results;
  return PVR_ERROR_NOT_IMPLEMENTED;
}

PVR_ERROR Client::GetTimersAmount(int& amount)
{
  amount = 0;
  return PVR_ERROR_NO_ERROR;
}

PVR_ERROR Client::GetTimers(kodi::addon::PVRTimersResultSet& results)
{
  (void)results;
  return PVR_ERROR_NOT_IMPLEMENTED;
}

PVR_ERROR Client::AddTimer(const kodi::addon::PVRTimer& timer)
{
  (void)timer;
  return PVR_ERROR_NOT_IMPLEMENTED;
}

PVR_ERROR Client::DeleteTimer(const kodi::addon::PVRTimer& timer)
{
  (void)timer;
  return PVR_ERROR_NOT_IMPLEMENTED;
}

PVR_ERROR Client::UpdateTimer(const kodi::addon::PVRTimer& timer)
{
  (void)timer;
  return PVR_ERROR_NOT_IMPLEMENTED;
}

PVR_ERROR Client::OpenLiveStream(const kodi::addon::PVRChannel& channel)
{
  (void)channel;
  return PVR_ERROR_NOT_IMPLEMENTED;
}

void Client::CloseLiveStream()
{
}

std::string Client::BuildBaseUrl() const
{
  std::ostringstream url;
  url << "http://" << m_settings.server_ip << ":" << m_settings.server_port;
  return url.str();
}

std::string Client::BuildLiveUrl(unsigned int channelId) const
{
  std::ostringstream url;
  url << BuildBaseUrl() << "/api/stream/live?channel_id=" << channelId;
  return url.str();
}

std::string Client::BuildDvrUrl() const
{
  return BuildBaseUrl() + "/dvr/playlist.m3u8";
}

std::string Client::BuildScheduleUrl() const
{
  return BuildBaseUrl() + "/api/schedule";
}
} // namespace eliteiptv
