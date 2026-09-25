#pragma once
#include "admission.h"
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <vector>

namespace rocell::usb_identity {
using Bytes = std::vector<std::uint8_t>;
enum class Op {
  MapEndpoint,
  DeviceId,
  Parent,
  DriverKey,
  HubInterface,
  HostController,
  OpenHub,
  HubInformation,
  ConnectionDriverKey,
  ConnectionEx,
  ConnectionExV2,
  DeviceDescriptor,
  LanguageDescriptor,
  SerialDescriptor,
  CloseHub
};
const char *op_name(Op);
struct Error {
  std::string code = "API_FAILED", domain = "CONTRACT";
  std::uint32_t native_code = 0;
};
struct Input {
  Op op;
  std::uint32_t target = 0, handle = 0, port = 0, maximum = 0;
  std::string text;
  std::uint16_t language = 0;
  std::uint8_t index = 0;
};
struct Result {
  bool ok = false;
  Error error;
  std::uint32_t number = 0, returned = 0;
  std::string text;
  Bytes bytes;
};
// One call is a bounded semantic API invocation, not one kernel/SetupAPI call.
// The adapter accepts only this closed operation enum: no caller IOCTL numbers.
class UsbIdentityApi {
public:
  virtual ~UsbIdentityApi() = default;
  virtual Result call(const Input &) = 0;
};
struct Limits {
  std::uint32_t calls = 128, hops = 8, hub_opens = 32, result_bytes = 65536;
  std::uint32_t duration_ms = 10000;
};
struct Call {
  std::uint32_t sequence = 0;
  std::string phase;
  Input input;
  Result result;
};
struct Hop {
  std::string hub_instance_id, hub_interface_path, downstream_driver_key;
  std::uint32_t connection_index = 0;
};
struct Mapping {
  std::optional<std::string> returned_endpoint, endpoint_instance_id,
      physical_usb_instance_id, physical_driver_key,
      host_controller_instance_id;
  std::vector<Hop> hops;
};
struct Device {
  Bytes raw;
  std::optional<std::string> vid, pid;
  std::optional<std::uint32_t> bcd_usb, serial_index;
};
struct Languages {
  Bytes raw;
  std::vector<std::uint16_t> ids;
};
struct Serial {
  std::uint16_t language = 0;
  Bytes raw;
  std::optional<std::string> value;
};
struct Link {
  Bytes ex_raw;
  std::optional<Bytes> v2_raw;
  std::optional<std::uint32_t> status, speed, protocols;
  std::optional<bool> operating, capable, plus_operating, plus_capable;
};
struct Observation {
  Request request;
  std::string outcome = "HELD";
  std::optional<Mapping> pre, post;
  std::optional<Device> device;
  std::optional<Languages> languages;
  std::vector<Serial> serials;
  std::optional<Link> link;
  std::vector<Call> calls;
  std::optional<Error> error;
  std::uint64_t elapsed = 0;
};
std::string serialize_observation(const Observation &);
std::string mapping_json(const Mapping &);
std::string json_quote(const std::string &);
std::string hex(const Bytes &);
std::string utf16(const Bytes &, bool terminal_null);
std::uint16_t u16(const Bytes &, std::size_t);
std::uint32_t u32(const Bytes &, std::size_t);
Observation
observe_usb_identity(UsbIdentityApi &, const Request &, const Limits &,
                     const std::function<bool()> &cancelled,
                     const std::function<std::uint64_t()> &milliseconds);
} // namespace rocell::usb_identity
