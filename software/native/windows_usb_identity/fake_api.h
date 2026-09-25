#pragma once
#include "observation.h"
#include <algorithm>
#include <map>
#include <stdexcept>

namespace rocell::usb_identity::test {
inline void put(Bytes &b, std::size_t offset, std::uint32_t n,
                unsigned count = 4) {
  for (unsigned k = 0; k < count; ++k)
    b.at(offset + k) = static_cast<std::uint8_t>(n >> (8 * k));
}
inline Bytes string_descriptor(const std::u16string &s) {
  Bytes b{static_cast<std::uint8_t>(2 + 2 * s.size()), 3};
  for (auto c : s) {
    b.push_back(static_cast<std::uint8_t>(c));
    b.push_back(static_cast<std::uint8_t>(c >> 8));
  }
  return b;
}
inline std::string endpoint(bool unicode = false) {
  return unicode
             ? "\\\\?\\usb#vid_1234&pid_5678#MODELED-\xe7\x9b\xb8\xe6\x9c\xba"
             : "\\\\?\\usb#vid_1234&pid_5678#MODELED-ONLY";
}
inline std::string instance() {
  return "USB\\VID_1234&PID_5678&MI_00\\MODELED-ENDPOINT";
}
inline Request request(bool unicode = false) {
  std::map<std::string, std::string> f;
  for (const auto &key :
       {"source_sha256", "operation_sha256", "selected_identity_sha256",
        "native_identity_sha256", "helper_sha256",
        "runtime_registration_sha256", "permit_sha256"})
    f[key] = json_quote(std::string(64, 'a'));
  f["schema"] = "\"rocell.native_usb_identity_admission_request.v1\"";
  f["attempt_id"] = "\"attempt-modeled-usb\"";
  f["session_id"] = "\"session-modeled-usb\"";
  f["endpoint"] = json_quote(endpoint(unicode));
  f["endpoint_sha256"] = json_quote(sha256(endpoint(unicode)));
  f["expected_device_instance_id"] = json_quote(instance());
  f["expected_device_instance_id_sha256"] = json_quote(sha256(instance()));
  f["native_duration_ms"] = "10000";
  f["admission_timeout_ms"] = "5000";
  std::string wire = "{";
  for (const auto &[key, value] : f) {
    if (wire.size() > 1)
      wire += ',';
    wire += json_quote(key) + ":" + value;
  }
  wire += '}';
  return parse_request(wire, sha256(wire));
}
inline std::string request_json(const Request &r) {
  std::string s = "{";
  for (const auto &[key, v] : r.fields) {
    if (s.size() > 1)
      s += ',';
    s += json_quote(key) + ":" + (v.number ? v.text : json_quote(v.text));
  }
  return s + '}';
}
class FakeApi final : public UsbIdentityApi {
public:
  std::string scenario;
  unsigned maps = 0, invocations = 0, open_calls = 0;
  std::map<std::uint32_t, std::uint32_t> live;
  explicit FakeApi(std::string name = "nominal") : scenario(std::move(name)) {}
  Bytes device() const {
    Bytes b(18, 0);
    b[0] = 18;
    b[1] = 1;
    put(b, 2, 0x300, 2);
    b[7] = 64;
    put(b, 8, 0x1234, 2);
    put(b, 10, 0x5678, 2);
    b[16] = scenario == "no-serial" ? 0 : 3;
    b[17] = 1;
    return b;
  }
  Result call(const Input &i) override {
    ++invocations;
    Result r;
    r.ok = true;
    auto text = [&](std::string s) {
      r.text = std::move(s);
      r.returned = static_cast<std::uint32_t>(r.text.size() + 1);
    };
    if (scenario == "api-failure" && i.op == Op::DriverKey) {
      r.ok = false;
      r.error = {"API_FAILED", "CM", 13};
      return r;
    }
    if (i.op == Op::MapEndpoint) {
      ++maps;
      r.number = 1;
      text(endpoint(scenario == "unicode"));
    } else if (i.op == Op::DeviceId) {
      static const std::map<std::uint32_t, std::string> ids = {
          {1, instance()},
          {2, "USB\\VID_1234&PID_5678\\MODELED-ONLY"},
          {3, "USB\\VID_2222&PID_3333\\MODELED-HUB"},
          {4, "USB\\ROOT_HUB30\\MODELED-ROOT"},
          {5, "PCI\\VEN_1111&DEV_2222\\MODELED-HOST"}};
      text(ids.at(i.target) +
           (scenario == "changed-device" && maps >= 2 && i.target == 1
                ? "-CHANGED"
                : ""));
    } else if (i.op == Op::Parent)
      r.number = i.target + 1;
    else if (i.op == Op::DriverKey)
      text(i.target == 2 ? "{MODELED-DRIVER}\\0001"
                         : "{MODELED-HUB-DRIVER}\\0002");
    else if (i.op == Op::HubInterface) {
      if (i.target == 3 || i.target == 4)
        text("\\\\?\\MODELED-HUB-" + std::to_string(i.target));
    } else if (i.op == Op::HostController) {
      if (i.target == 5)
        text("\\\\?\\MODELED-HOST");
    } else if (i.op == Op::OpenHub) {
      ++open_calls;
      if (!live.empty())
        throw std::runtime_error("Multiple fake handles");
      live[i.handle] = i.text.back() == '3' ? 3 : 4;
    } else if (i.op == Op::CloseHub) {
      if (!live.count(i.handle))
        throw std::runtime_error("Invalid fake close");
      if (scenario == "close-failure") {
        r.ok = false;
        r.error = {"API_FAILED", "WIN32", 6};
      } else
        live.erase(i.handle);
    } else {
      if (!live.count(i.handle))
        throw std::runtime_error("Unowned fake I/O");
      const auto node = live.at(i.handle);
      if (i.op == Op::HubInformation) {
        r.number = scenario == "call-limit" ? 255 : 2;
        r.returned = 76;
      } else if (i.op == Op::ConnectionDriverKey)
        text(node == 3 ? "{MODELED-DRIVER}\\0001"
                       : "{MODELED-HUB-DRIVER}\\0002");
      else if (i.op == Op::ConnectionEx) {
        r.bytes.resize(scenario == "maximum-raw" ? 4096
                       : scenario == "pipes"     ? 46
                                                 : 35,
                       0);
        put(r.bytes, 0, i.port);
        auto d = device();
        std::copy(d.begin(), d.end(), r.bytes.begin() + 4);
        r.bytes[23] = scenario == "usb2" ? 2 : 3;
        r.bytes[24] = node == 4 ? 1 : 0;
        put(r.bytes, 31,
            i.port == 2 || scenario == "duplicate-mapping" ? 1 : 0);
        if (scenario == "pipes")
          put(r.bytes, 27, 1);
        if (scenario == "maximum-raw")
          put(r.bytes, 27, 369);
        if (scenario == "malformed-ex")
          r.bytes[24] = 2;
      } else if (i.op == Op::ConnectionExV2) {
        if (scenario == "v2-unavailable") {
          r.ok = false;
          r.error = {"API_FAILED", "WIN32", 1};
          return r;
        }
        r.bytes.resize(16, 0);
        put(r.bytes, 0, i.port);
        put(r.bytes, 4, 16);
        put(r.bytes, 8, 7);
        put(r.bytes, 12,
            scenario == "usb2"           ? 2
            : scenario == "malformed-v2" ? 4
                                         : 3);
      } else if (i.op == Op::DeviceDescriptor) {
        r.bytes = device();
        if (scenario == "malformed-device")
          r.bytes[0] = 17;
      } else if (i.op == Op::LanguageDescriptor) {
        r.bytes = {4, 3, 9, 4};
        if (scenario == "language-conflict") {
          r.bytes = {6, 3, 9, 4, 17, 4};
        }
        if (scenario == "malformed-language")
          r.bytes[0] = 8;
      } else if (i.op == Op::SerialDescriptor) {
        r.bytes =
            string_descriptor(scenario == "unicode" ? u"MODELED-相机-\U0001f4f7"
                              : i.language == 0x411 ? u"DIFFERENT-MODELED"
                                                    : u"MODELED-ONLY");
        if (scenario == "malformed-serial")
          r.bytes = {4, 3, 0, 0xd8};
      }
      if (!r.bytes.empty())
        r.returned = static_cast<std::uint32_t>(
            r.bytes.size() + (i.op >= Op::DeviceDescriptor ? 12 : 0));
    }
    return r;
  }
};
} // namespace rocell::usb_identity::test
