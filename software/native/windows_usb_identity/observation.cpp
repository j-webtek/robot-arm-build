#include "observation.h"
#include <algorithm>
#include <set>
#include <stdexcept>

namespace rocell::usb_identity {
namespace {
void need(bool ok, const char *code) {
  if (!ok)
    throw std::runtime_error(code);
}
bool usb_instance(const std::string &s) {
  return s.rfind("USB\\VID_", 0) == 0 && s.find("&PID_") != std::string::npos;
}
std::string word(std::uint16_t n) {
  return hex(
      Bytes{static_cast<std::uint8_t>(n >> 8), static_cast<std::uint8_t>(n)});
}
class Engine {
  UsbIdentityApi &api;
  const Limits &limits;
  const std::function<bool()> &cancelled;
  const std::function<std::uint64_t()> &clock;
  std::uint64_t start;
  std::uint32_t token = 0, live = 0, opens = 0;
  bool close_attempted = false;

public:
  Observation out;
  std::string phase = "PRE";
  Engine(UsbIdentityApi &a, const Request &r, const Limits &l,
         const std::function<bool()> &c,
         const std::function<std::uint64_t()> &now)
      : api(a), limits(l), cancelled(c), clock(now), start(now()) {
    out.request = r;
    out.calls.reserve(128);
  }
  void checkpoint() {
    need(!cancelled(), "CANCELLED");
    auto now = clock();
    need(now >= start && now - start < limits.duration_ms, "TIMEOUT");
  }
  Result invoke(Input input, bool required = true) {
    if (input.op != Op::CloseHub) {
      checkpoint();
      const auto reserve = (live || input.op == Op::OpenHub) ? 1u : 0u;
      need(out.calls.size() + reserve < limits.calls, "CALL_LIMIT");
      // Reserve the maximum raw hex, duplicate selected subject, escaped text
      // projection and cleanup before I/O. Never discard a returned
      // observation.
      const auto reserve_bytes =
          32768 +
          (input.op == Op::MapEndpoint ? 2 * json_quote(input.text).size() : 0);
      need(serialize_observation(out).size() + reserve_bytes <
               limits.result_bytes,
           "BYTE_LIMIT");
    }
    // Allocate/copy the complete trace input before entering the native seam.
    out.calls.push_back({static_cast<std::uint32_t>(out.calls.size() + 1),
                         phase, input, Result{}});
    try {
      out.calls.back().result = api.call(input);
    } catch (...) {
      out.calls.back().result.error = {"API_FAILED", "CONTRACT", 0};
    }
    const auto &r = out.calls.back().result;
    if (input.op == Op::OpenHub && r.ok) {
      live = input.handle;
      close_attempted = false;
    }
    if (input.op == Op::CloseHub && r.ok)
      live = 0;
    need(r.returned <= input.maximum && r.bytes.size() <= input.maximum &&
             r.text.size() <= 4096,
         "BYTE_LIMIT");
    if (required && !r.ok) {
      out.error = r.error;
      throw std::runtime_error(r.error.code);
    }
    // Preserve the returned data before checking time/cancellation in caller.
    return r;
  }
  Result query(Op op, std::uint32_t target = 0, std::string text = "",
               std::uint32_t port = 0, std::uint32_t maximum = 4096,
               bool required = true) {
    return invoke({op, target, live, port, maximum, std::move(text), 0, 0},
                  required);
  }
  void open(std::uint32_t target, const std::string &path) {
    need(!live, "CLOSE_FAILED");
    need(opens < limits.hub_opens, "CALL_LIMIT");
    ++opens;
    Input i{Op::OpenHub, target, ++token, 0, 0, path, 0, 0};
    invoke(i);
  }
  void close() {
    if (!live || close_attempted)
      return;
    close_attempted = true;
    const auto old = phase;
    phase = "CLEANUP";
    auto r = invoke({Op::CloseHub, 0, live, 0, 0, "", 0, 0}, false);
    phase = old;
    if (!r.ok) {
      out.error = Error{"CLOSE_FAILED", r.error.domain, r.error.native_code};
      throw std::runtime_error("CLOSE_FAILED");
    }
  }
  static void ex_valid(const Bytes &raw, std::uint32_t port) {
    need(raw.size() >= 35 && raw.size() <= 4096 && u32(raw, 0) == port &&
             raw[23] <= 3 && raw[24] <= 1 && u32(raw, 31) <= 10,
         "DESCRIPTOR_MALFORMED");
    need(u32(raw, 27) <= (4096 - 35) / 11 &&
             raw.size() >= 35 + 11 * u32(raw, 27),
         "DESCRIPTOR_MALFORMED");
  }
  void mapping(Mapping &m) {
    // Walk the selected endpoint's real CM ancestry. The physical USB node is
    // the child immediately below the first hub, not an inferred serial suffix
    // or a parent driver-property replacement for the camera function driver.
    auto mapped = query(Op::MapEndpoint, 0, out.request.endpoint());
    m.returned_endpoint = mapped.text;
    need(mapped.text == out.request.endpoint(), "ENDPOINT_MISMATCH");
    std::uint32_t current = mapped.number;
    need(current != 0, "HUB_MAPPING_MISSING");
    auto instance = query(Op::DeviceId, current).text;
    m.endpoint_instance_id = instance;
    need(instance == out.request.expected_instance(), "DEVICE_CHANGED");
    std::set<std::uint32_t> seen{current};
    bool physical = false;
    for (unsigned ancestor = 0; ancestor < 24; ++ancestor) {
      auto parent = query(Op::Parent, current, {}, 0, 0).number;
      need(parent != 0 && seen.insert(parent).second, "ANCESTRY_AMBIGUOUS");
      auto hub = query(Op::HubInterface, parent);
      if (hub.text.empty()) {
        if (physical) {
          auto host = query(Op::HostController, parent);
          need(!host.text.empty(), "USB_ANCESTOR_MISSING");
          m.host_controller_instance_id = query(Op::DeviceId, parent).text;
          checkpoint();
          return;
        }
        current = parent;
        instance = query(Op::DeviceId, current).text;
        continue;
      }
      need(m.hops.size() < limits.hops, "HOP_LIMIT");
      const auto key = query(Op::DriverKey, current).text;
      need(!key.empty(), "HUB_MAPPING_MISSING");
      if (!physical) {
        need(usb_instance(instance), "USB_ANCESTOR_MISSING");
        m.physical_usb_instance_id = instance;
        m.physical_driver_key = key;
        physical = true;
      }
      auto hub_id = query(Op::DeviceId, parent).text;
      open(parent, hub.text);
      const auto count = query(Op::HubInformation, parent).number;
      need(count >= 1 && count <= 255, "DESCRIPTOR_MALFORMED");
      std::vector<std::uint32_t> matches;
      // Inspect every port in this bounded hub before selecting the unique
      // downstream driver-key match; a failed/incomplete scan is not absence.
      for (std::uint32_t port = 1; port <= count; ++port) {
        auto ex = query(Op::ConnectionEx, parent, {}, port, 4096);
        ex_valid(ex.bytes, port);
        const auto status = u32(ex.bytes, 31);
        if (status == 0)
          continue;
        need(status == 1, "NOT_CONNECTED");
        auto driver = query(Op::ConnectionDriverKey, parent, {}, port);
        if (driver.text == key)
          matches.push_back(port);
      }
      need(matches.size() == 1,
           matches.empty() ? "HUB_MAPPING_MISSING" : "HUB_MAPPING_AMBIGUOUS");
      // These three strings were read on different calls. Account for their
      // combined duplicate hop projection before adding it, keeping the raw
      // trace and reserved close available even for maximum Unicode values.
      need(serialize_observation(out).size() + json_quote(hub_id).size() +
                   json_quote(hub.text).size() + json_quote(key).size() + 2048 <
               limits.result_bytes,
           "BYTE_LIMIT");
      m.hops.push_back({hub_id, hub.text, key, matches.front()});
      close();
      current = parent;
      instance = hub_id;
    }
    throw std::runtime_error("HOP_LIMIT");
  }
  void observe() {
    auto &h = out.pre->hops.front();
    open(0, h.hub_interface_path);
    auto ex = query(Op::ConnectionEx, 0, {}, h.connection_index, 4096);
    out.link = Link{};
    out.link->ex_raw = ex.bytes;
    ex_valid(ex.bytes, h.connection_index);
    out.link->status = u32(ex.bytes, 31);
    out.link->speed = ex.bytes[23];
    need(*out.link->status == 1, "NOT_CONNECTED");
    auto v2 = query(Op::ConnectionExV2, 0, {}, h.connection_index, 16, false);
    // Operating and capable bits are independent categorical observations.
    // Neither bcdUSB nor a capability bit is converted to negotiated Mbps.
    if (v2.ok) {
      out.link->v2_raw = v2.bytes;
      need(v2.bytes.size() == 16 && u32(v2.bytes, 0) == h.connection_index &&
               u32(v2.bytes, 4) == 16 && (u32(v2.bytes, 8) & ~7u) == 0 &&
               (u32(v2.bytes, 12) & ~15u) == 0,
           "DESCRIPTOR_MALFORMED");
      auto f = u32(v2.bytes, 12);
      need(!(f & 4) || (f & 1), "DESCRIPTOR_MALFORMED");
      out.link->protocols = u32(v2.bytes, 8);
      out.link->operating = (f & 1) != 0;
      out.link->capable = (f & 2) != 0;
      out.link->plus_operating = (f & 4) != 0;
      out.link->plus_capable = (f & 8) != 0;
    }
    auto device = query(Op::DeviceDescriptor, 0, {}, h.connection_index, 30);
    out.device = Device{};
    out.device->raw = device.bytes;
    need(device.bytes.size() == 18 && device.bytes[0] == 18 &&
             device.bytes[1] == 1,
         "DESCRIPTOR_MALFORMED");
    out.device->vid = word(u16(device.bytes, 8));
    out.device->pid = word(u16(device.bytes, 10));
    out.device->bcd_usb = u16(device.bytes, 2);
    out.device->serial_index = device.bytes[16];
    need(std::equal(device.bytes.begin(), device.bytes.end(),
                    ex.bytes.begin() + 4),
         "DEVICE_CHANGED");
    const auto expected =
        "USB\\VID_" + *out.device->vid + "&PID_" + *out.device->pid;
    auto id = *out.pre->physical_usb_instance_id;
    std::transform(id.begin(), id.end(), id.begin(), [](unsigned char c) {
      return static_cast<char>(c >= 'A' && c <= 'Z' ? c + 32 : c);
    });
    auto lowered = expected;
    std::transform(
        lowered.begin(), lowered.end(), lowered.begin(), [](unsigned char c) {
          return static_cast<char>(c >= 'A' && c <= 'Z' ? c + 32 : c);
        });
    need(id.rfind(lowered, 0) == 0, "DEVICE_CHANGED");
    need(*out.device->serial_index != 0, "SERIAL_NOT_PRESENT");
    auto langs = query(Op::LanguageDescriptor, 0, {}, h.connection_index, 267);
    out.languages = Languages{langs.bytes, {}};
    need(langs.bytes.size() >= 4 && langs.bytes.size() <= 10 &&
             langs.bytes.size() % 2 == 0 &&
             langs.bytes[0] == langs.bytes.size() && langs.bytes[1] == 3,
         "DESCRIPTOR_MALFORMED");
    std::set<std::uint16_t> unique;
    for (std::size_t j = 2; j < langs.bytes.size(); j += 2) {
      auto language = u16(langs.bytes, j);
      need(language != 0 && unique.insert(language).second,
           "DESCRIPTOR_MALFORMED");
    }
    for (std::size_t j = 2; j < langs.bytes.size(); j += 2)
      out.languages->ids.push_back(u16(langs.bytes, j));
    for (auto language : out.languages->ids) {
      // The exact device iSerialNumber and advertised LANGID are retained in
      // the call trace. No product label, location or instance-ID fallback.
      Input input{Op::SerialDescriptor,
                  0,
                  live,
                  h.connection_index,
                  267,
                  "",
                  language,
                  static_cast<std::uint8_t>(*out.device->serial_index)};
      auto serial = invoke(input);
      out.serials.push_back({language, serial.bytes, std::nullopt});
      need(serial.bytes.size() >= 4 && serial.bytes.size() <= 255 &&
               serial.bytes.size() % 2 == 0 &&
               serial.bytes[0] == serial.bytes.size() && serial.bytes[1] == 3,
           "DESCRIPTOR_MALFORMED");
      Bytes content(serial.bytes.begin() + 2, serial.bytes.end());
      out.serials.back().value = utf16(content, false);
    }
    for (const auto &s : out.serials)
      need(s.value == out.serials.front().value, "SERIAL_AMBIGUOUS");
    checkpoint();
    close();
  }
  Observation run() {
    try {
      need(limits.calls >= 2 && limits.calls <= 128 && limits.hops >= 1 &&
               limits.hops <= 8 && limits.hub_opens >= 1 &&
               limits.hub_opens <= 32 && limits.result_bytes >= 16384 &&
               limits.result_bytes <= 65536 && limits.duration_ms >= 1 &&
               limits.duration_ms <= 10000,
           "REQUEST_INVALID");
      out.pre = Mapping{};
      mapping(*out.pre);
      phase = "OBSERVE";
      observe();
      phase = "POST";
      out.post = Mapping{};
      mapping(*out.post);
      need(mapping_json(*out.pre) == mapping_json(*out.post), "DEVICE_CHANGED");
      checkpoint();
      out.outcome = "OBSERVED";
    } catch (const std::exception &e) {
      static const std::set<std::string> codes = {"REQUEST_INVALID",
                                                  "ENDPOINT_MISMATCH",
                                                  "DEVICE_CHANGED",
                                                  "USB_ANCESTOR_MISSING",
                                                  "ANCESTRY_AMBIGUOUS",
                                                  "HUB_MAPPING_MISSING",
                                                  "HUB_MAPPING_AMBIGUOUS",
                                                  "PORT_MISMATCH",
                                                  "NOT_CONNECTED",
                                                  "SERIAL_NOT_PRESENT",
                                                  "SERIAL_AMBIGUOUS",
                                                  "DESCRIPTOR_MALFORMED",
                                                  "UTF16_INVALID",
                                                  "PROPERTY_TYPE",
                                                  "BYTE_LIMIT",
                                                  "CALL_LIMIT",
                                                  "HOP_LIMIT",
                                                  "TIMEOUT",
                                                  "CANCELLED",
                                                  "API_FAILED",
                                                  "CLOSE_FAILED",
                                                  "POST_MAPPING_FAILED"};
      if (!out.error)
        out.error = Error{codes.count(e.what()) ? e.what() : "API_FAILED",
                          "CONTRACT", 0};
    }
    try {
      close();
    } catch (const std::exception &) {
      out.outcome = "HELD";
    }
    if (out.error || live)
      out.outcome = "HELD";
    const auto now = clock();
    out.elapsed = now >= start ? now - start : 0;
    if (out.elapsed >= limits.duration_ms && !out.error) {
      out.error = Error{"TIMEOUT", "CONTRACT", 0};
      out.outcome = "HELD";
    }
    return out;
  }
};
} // namespace
Observation observe_usb_identity(UsbIdentityApi &api, const Request &r,
                                 const Limits &limits,
                                 const std::function<bool()> &cancelled,
                                 const std::function<std::uint64_t()> &clock) {
  return Engine(api, r, limits, cancelled, clock).run();
}
} // namespace rocell::usb_identity
