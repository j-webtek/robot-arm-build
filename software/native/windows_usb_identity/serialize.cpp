#include "observation.h"
#include <map>
#include <set>
#include <stdexcept>

namespace rocell::usb_identity {
namespace {
using P = std::pair<std::string, std::string>;
std::string object(std::initializer_list<P> fields) {
  std::string out = "{";
  bool first = true;
  for (const auto &[k, v] : fields) {
    if (!first)
      out += ',';
    first = false;
    out += json_quote(k) + ":" + v;
  }
  return out + '}';
}
template <class T, class F> std::string array(const T &items, F f) {
  std::string out = "[";
  bool first = true;
  for (const auto &item : items) {
    if (!first)
      out += ',';
    first = false;
    out += f(item);
  }
  return out + ']';
}
std::string number(std::uint64_t n) { return std::to_string(n); }
std::string nullable(const std::optional<std::string> &v) {
  return v ? json_quote(*v) : "null";
}
std::string nullable(const std::optional<std::uint32_t> &v) {
  return v ? number(*v) : "null";
}
std::string nullable(const std::optional<bool> &v) {
  return v ? (*v ? "true" : "false") : "null";
}
std::string token(std::uint32_t n) { return n ? number(n) : "null"; }
std::string error(const Error &e) {
  return object({{"code", json_quote(e.code)},
                 {"domain", json_quote(e.domain)},
                 {"native_code", number(e.native_code)}});
}
} // namespace
std::string json_quote(const std::string &s) {
  std::string out = "\"";
  static const char *h = "0123456789abcdef";
  auto escaped = [&](std::uint32_t n) {
    out += "\\u";
    for (int shift = 12; shift >= 0; shift -= 4)
      out += h[(n >> shift) & 15];
  };
  for (std::size_t i = 0; i < s.size(); ++i) {
    auto c = static_cast<unsigned char>(s[i]);
    if (c == '"' || c == '\\') {
      out += '\\';
      out += static_cast<char>(c);
    } else if (c < 32)
      escaped(c);
    else if (c < 128)
      out += static_cast<char>(c);
    else {
      unsigned count = 0;
      std::uint32_t cp = 0, minimum = 0;
      if (c >= 0xc2 && c <= 0xdf) {
        count = 1;
        cp = c & 31;
        minimum = 0x80;
      } else if (c >= 0xe0 && c <= 0xef) {
        count = 2;
        cp = c & 15;
        minimum = 0x800;
      } else if (c >= 0xf0 && c <= 0xf4) {
        count = 3;
        cp = c & 7;
        minimum = 0x10000;
      } else
        throw std::runtime_error("UTF16_INVALID");
      while (count--) {
        if (++i >= s.size())
          throw std::runtime_error("UTF16_INVALID");
        auto x = static_cast<unsigned char>(s[i]);
        if ((x & 0xc0) != 0x80)
          throw std::runtime_error("UTF16_INVALID");
        cp = (cp << 6) | (x & 63);
      }
      if (cp < minimum || cp > 0x10ffff || (cp >= 0xd800 && cp <= 0xdfff))
        throw std::runtime_error("UTF16_INVALID");
      if (cp < 0x10000)
        escaped(cp);
      else {
        cp -= 0x10000;
        escaped(0xd800 + (cp >> 10));
        escaped(0xdc00 + (cp & 1023));
      }
    }
  }
  return out + '"';
}
std::string hex(const Bytes &b) {
  static const char *h = "0123456789abcdef";
  std::string s;
  for (auto c : b) {
    s += h[c >> 4];
    s += h[c & 15];
  }
  return s;
}
std::uint16_t u16(const Bytes &b, std::size_t i) {
  return static_cast<std::uint16_t>(b.at(i) |
                                    (std::uint16_t(b.at(i + 1)) << 8));
}
std::uint32_t u32(const Bytes &b, std::size_t i) {
  return u16(b, i) | (std::uint32_t(u16(b, i + 2)) << 16);
}
std::string utf16(const Bytes &b, bool terminal_null) {
  if (b.empty() || b.size() % 2)
    throw std::runtime_error("UTF16_INVALID");
  std::size_t end = b.size();
  if (terminal_null) {
    if (u16(b, end - 2) != 0)
      throw std::runtime_error("UTF16_INVALID");
    end -= 2;
  }
  std::string s;
  for (std::size_t i = 0; i < end; i += 2) {
    std::uint32_t c = u16(b, i);
    if (c < 32 || c == 127)
      throw std::runtime_error("UTF16_INVALID");
    if (c >= 0xd800 && c <= 0xdbff) {
      if (i + 3 >= end)
        throw std::runtime_error("UTF16_INVALID");
      auto low = u16(b, i + 2);
      if (low < 0xdc00 || low > 0xdfff)
        throw std::runtime_error("UTF16_INVALID");
      c = 0x10000 + ((c - 0xd800) << 10) + low - 0xdc00;
      i += 2;
    } else if (c >= 0xdc00 && c <= 0xdfff)
      throw std::runtime_error("UTF16_INVALID");
    if (c < 0x80)
      s += static_cast<char>(c);
    else if (c < 0x800) {
      s += static_cast<char>(0xc0 | (c >> 6));
      s += static_cast<char>(0x80 | (c & 63));
    } else if (c < 0x10000) {
      s += static_cast<char>(0xe0 | (c >> 12));
      s += static_cast<char>(0x80 | ((c >> 6) & 63));
      s += static_cast<char>(0x80 | (c & 63));
    } else {
      s += static_cast<char>(0xf0 | (c >> 18));
      s += static_cast<char>(0x80 | ((c >> 12) & 63));
      s += static_cast<char>(0x80 | ((c >> 6) & 63));
      s += static_cast<char>(0x80 | (c & 63));
    }
  }
  if (s.empty())
    throw std::runtime_error("UTF16_INVALID");
  return s;
}
const char *op_name(Op op) {
  static const char *names[] = {"MAP_ENDPOINT",
                                "DEVICE_ID",
                                "PARENT",
                                "DRIVER_KEY_PROPERTY",
                                "HUB_INTERFACE",
                                "HOST_CONTROLLER_PROPERTY",
                                "OPEN_HUB",
                                "HUB_INFORMATION",
                                "CONNECTION_DRIVER_KEY",
                                "CONNECTION_EX",
                                "CONNECTION_EX_V2",
                                "DEVICE_DESCRIPTOR",
                                "LANGUAGE_DESCRIPTOR",
                                "SERIAL_DESCRIPTOR",
                                "CLOSE_HUB"};
  return names[static_cast<unsigned>(op)];
}
std::string mapping_json(const Mapping &m) {
  return object(
      {{"returned_endpoint", nullable(m.returned_endpoint)},
       {"endpoint_instance_id", nullable(m.endpoint_instance_id)},
       {"physical_usb_instance_id", nullable(m.physical_usb_instance_id)},
       {"physical_driver_key", nullable(m.physical_driver_key)},
       {"host_controller_instance_id", nullable(m.host_controller_instance_id)},
       {"hops", array(m.hops, [](const Hop &h) {
          return object(
              {{"hub_instance_id", json_quote(h.hub_instance_id)},
               {"hub_interface_path", json_quote(h.hub_interface_path)},
               {"connection_index", number(h.connection_index)},
               {"downstream_driver_key", json_quote(h.downstream_driver_key)}});
        })}});
}
std::string serialize_observation(const Observation &o) {
  std::string d = "null", l = "null", link = "null";
  if (o.device) {
    const auto &x = *o.device;
    d = object({{"raw_hex", json_quote(hex(x.raw))},
                {"vid", nullable(x.vid)},
                {"pid", nullable(x.pid)},
                {"bcd_usb", nullable(x.bcd_usb)},
                {"i_serial_number", nullable(x.serial_index)}});
  }
  if (o.languages) {
    const auto &x = *o.languages;
    l = object(
        {{"raw_hex", json_quote(hex(x.raw))},
         {"language_ids", array(x.ids, [](auto n) { return number(n); })}});
  }
  if (o.link) {
    const auto &x = *o.link;
    link = object(
        {{"connection_status", nullable(x.status)},
         {"ex_speed", nullable(x.speed)},
         {"ex_v2_available", x.v2_raw ? "true" : "false"},
         {"supported_usb_protocols", nullable(x.protocols)},
         {"operating_superspeed_or_higher", nullable(x.operating)},
         {"capable_superspeed_or_higher", nullable(x.capable)},
         {"operating_superspeed_plus_or_higher", nullable(x.plus_operating)},
         {"capable_superspeed_plus_or_higher", nullable(x.plus_capable)},
         {"ex_raw_hex", json_quote(hex(x.ex_raw))},
         {"ex_v2_raw_hex", x.v2_raw ? json_quote(hex(*x.v2_raw)) : "null"}});
  }
  std::uint32_t oa = 0, os = 0, ia = 0, is = 0, ds = 0, ca = 0, cs = 0,
                peak = 0;
  std::uint64_t returned = 0;
  std::set<std::uint32_t> live;
  for (const auto &c : o.calls) {
    const auto op = c.input.op;
    returned += c.result.returned;
    if (op == Op::OpenHub) {
      ++oa;
      if (c.result.ok) {
        ++os;
        live.insert(c.input.handle);
        if (live.size() > peak)
          peak = static_cast<std::uint32_t>(live.size());
      }
    }
    if (op >= Op::HubInformation && op <= Op::SerialDescriptor) {
      ++ia;
      if (c.result.ok)
        ++is;
    }
    if (op >= Op::DeviceDescriptor && op <= Op::SerialDescriptor)
      ++ds;
    if (op == Op::CloseHub) {
      ++ca;
      if (c.result.ok) {
        ++cs;
        live.erase(c.input.handle);
      }
    }
  }
  const auto accounting =
      object({{"api_calls", number(o.calls.size())},
              {"hub_open_attempts", number(oa)},
              {"hub_open_successes", number(os)},
              {"ioctl_attempts", number(ia)},
              {"ioctl_successes", number(is)},
              {"descriptor_requests", number(ds)},
              {"close_attempts", number(ca)},
              {"close_successes", number(cs)},
              {"peak_open_handles", number(peak)},
              {"remaining_open_handles", number(live.size())},
              {"returned_bytes", number(returned)}});
  return object(
      {{"schema", "\"rocell.windows_usb_identity.v1\""},
       {"request_sha256", json_quote(o.request.hash)},
       {"requested_endpoint", json_quote(o.request.endpoint())},
       {"expected_device_instance_id",
        json_quote(o.request.expected_instance())},
       {"outcome", json_quote(o.outcome)},
       {"pre_mapping", o.pre ? mapping_json(*o.pre) : "null"},
       {"post_mapping", o.post ? mapping_json(*o.post) : "null"},
       {"device_descriptor", d},
       {"languages", l},
       {"serial_descriptors", array(o.serials,
                                    [](const Serial &s) {
                                      return object(
                                          {{"language_id", number(s.language)},
                                           {"raw_hex", json_quote(hex(s.raw))},
                                           {"value", nullable(s.value)}});
                                    })},
       {"link", link},
       {"accounting", accounting},
       {"calls",
        array(o.calls,
              [](const Call &c) {
                return object(
                    {{"sequence", number(c.sequence)},
                     {"phase", json_quote(c.phase)},
                     {"operation", json_quote(op_name(c.input.op))},
                     {"handle_id", token(c.input.handle)},
                     {"target_id", token(c.input.target)},
                     {"connection_index", token(c.input.port)},
                     {"requested_bytes", number(c.input.maximum)},
                     {"returned_bytes", number(c.result.returned)},
                     {"returned_raw_hex",
                      c.result.ok && (c.input.op == Op::ConnectionEx ||
                                      c.input.op == Op::ConnectionExV2 ||
                                      (c.input.op >= Op::DeviceDescriptor &&
                                       c.input.op <= Op::SerialDescriptor))
                          ? json_quote(hex(c.result.bytes))
                          : "null"},
                     {"descriptor_index",
                      c.input.op >= Op::DeviceDescriptor &&
                              c.input.op <= Op::SerialDescriptor
                          ? number(c.input.index)
                          : "null"},
                     {"language_id", c.input.op >= Op::DeviceDescriptor &&
                                             c.input.op <= Op::SerialDescriptor
                                         ? number(c.input.language)
                                         : "null"},
                     {"status", c.result.ok ? "\"OK\"" : "\"ERROR\""},
                     {"error_domain",
                      json_quote(c.result.ok ? "NONE" : c.result.error.domain)},
                     {"error_code",
                      number(c.result.ok ? 0 : c.result.error.native_code)},
                     {"observed_text", c.result.text.empty()
                                           ? "null"
                                           : json_quote(c.result.text)},
                     {"observed_number",
                      c.result.ok && (c.input.op == Op::MapEndpoint ||
                                      c.input.op == Op::Parent ||
                                      c.input.op == Op::HubInformation)
                          ? number(c.result.number)
                          : "null"}});
              })},
       {"error", o.error ? error(*o.error) : "null"},
       {"elapsed_ms", number(o.elapsed)}});
}
} // namespace rocell::usb_identity
