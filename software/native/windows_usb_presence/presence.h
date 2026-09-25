#pragma once
#include "../windows_usb_identity/admission.h"
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace rocell::usb_presence {
inline constexpr std::size_t request_limit = 8192, output_limit = 65536;
inline constexpr std::uint32_t max_chars = 8192, max_ids = 64;
inline constexpr std::uint32_t duration_ms = 2000, sample_count = 2;
using Fields = rocell::usb_identity::Fields;
using rocell::usb_identity::sha256;
struct Request {
  Fields fields;
  std::string payload, hash, target, filter;
};
std::string quote(const std::string &);
std::string upper_ascii(std::string);
std::string device_filter(const std::string &);
Request parse_request(const std::string &, const std::string &);
struct ApiResult {
  std::uint32_t code = 0, required_chars = 0;
  std::vector<wchar_t> multi_sz;
};
// Fixed present physical USB-device-ID filter only; never a raw flag/command
// API.
class PresenceApi {
public:
  virtual ~PresenceApi() = default;
  virtual ApiResult size(const std::string &filter) = 0;
  virtual ApiResult list(const std::string &filter, std::uint32_t capacity) = 0;
};
struct Moment {
  std::uint64_t monotonic_ms = 0, utc_ns = 0;
};
struct Sample {
  Moment start, finish;
  std::uint32_t required_chars = 0, used_chars = 0, api_calls = 0;
  std::optional<std::uint32_t> native_code;
  bool complete = false, target_present = false;
  std::vector<std::string> ids;
  std::string error;
};
struct Observation {
  Request request;
  std::string origin, outcome = "HELD", error;
  Moment start, finish;
  std::vector<Sample> samples;
};
Observation observe(PresenceApi &, const Request &, const std::string &origin,
                    const std::function<bool()> &cancelled,
                    const std::function<Moment()> &clock);
std::string serialize(const Observation &);
// Closed READY/RELEASE entry shared by production and separately linked
// fixture.
struct Admission {
  Request request;
  std::uint32_t pid = 0;
  std::string challenge;
};
Admission admit(const std::vector<std::wstring> &);
void publish(const Admission &, const Observation &);
Moment windows_clock();
} // namespace rocell::usb_presence
