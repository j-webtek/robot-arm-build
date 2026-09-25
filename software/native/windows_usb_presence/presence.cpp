#include "presence.h"
#include <algorithm>
#include <set>
#include <stdexcept>

namespace rocell::usb_presence {
namespace {
class PresenceFailure final : public std::runtime_error {
public:
  explicit PresenceFailure(const char *code) : std::runtime_error(code) {}
};
void need(bool yes, const char *code) {
  if (!yes)
    throw PresenceFailure(code);
}
bool hash(const std::string &s) {
  return s.size() == 64 &&
         s.find_first_not_of("0123456789abcdef") == std::string::npos;
}
bool identifier(const std::string &s) {
  if (s.empty() || s.size() > 96)
    return false;
  const auto alnum = [](char c) {
    return (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9');
  };
  if (!alnum(s[0]))
    return false;
  return std::all_of(s.begin(), s.end(), [&](char c) {
    return alnum(c) || c == '_' || c == '-' || c == '.';
  });
}
void parse_list(Sample &sample, const std::vector<wchar_t> &raw,
                const Request &r) {
  need(raw.size() == sample.required_chars && !raw.empty(),
       "LIST_CAPACITY_MISMATCH");
  std::set<std::string> seen;
  std::size_t pos = 0;
  while (true) {
    need(pos < raw.size(), "MULTI_SZ_TERMINATOR_REQUIRED");
    if (raw[pos] == 0) {
      sample.used_chars = static_cast<std::uint32_t>(pos + 1);
      break;
    }
    std::string id;
    while (pos < raw.size() && raw[pos] != 0) {
      need(raw[pos] >= 33 && raw[pos] < 127, "INSTANCE_ASCII_REQUIRED");
      id += static_cast<char>(raw[pos++]);
      need(id.size() < 200, "INSTANCE_LENGTH_LIMIT");
    }
    need(pos < raw.size(), "MULTI_SZ_TERMINATOR_REQUIRED");
    ++pos;
    need(upper_ascii(device_filter(id)) == upper_ascii(r.filter),
         "FILTER_RESULT_MISMATCH");
    need(seen.insert(upper_ascii(id)).second, "DUPLICATE_INSTANCE");
    need(sample.ids.size() < max_ids, "INSTANCE_COUNT_LIMIT");
    sample.ids.push_back(id);
  }
  sample.target_present = seen.count(upper_ascii(r.target)) == 1;
}
std::string moment_json(const Moment &m) {
  return "{\"monotonic_ms\":" + std::to_string(m.monotonic_ms) +
         ",\"utc_ns\":" + std::to_string(m.utc_ns) + "}";
}
} // namespace

std::string quote(const std::string &s) {
  std::string result = "\"";
  for (const char c : s) {
    need(c >= 32 && c < 127, "ASCII_JSON_REQUIRED");
    if (c == '\\' || c == '"')
      result += '\\';
    result += c;
  }
  return result + '"';
}
std::string upper_ascii(std::string s) {
  for (auto &c : s)
    if (c >= 'a' && c <= 'z')
      c = static_cast<char>(c - 'a' + 'A');
  return s;
}
std::string device_filter(const std::string &id) {
  need(!id.empty() && id.size() < 200, "PHYSICAL_INSTANCE_REQUIRED");
  for (const char c : id)
    need(c >= 33 && c < 127, "INSTANCE_ASCII_REQUIRED");
  const auto key = upper_ascii(id);
  const auto split = key.find('\\', 4);
  need(key.substr(0, 8) == "USB\\VID_" && split != std::string::npos &&
           split + 1 < key.size() &&
           key.find('\\', split + 1) == std::string::npos,
       "PHYSICAL_INSTANCE_REQUIRED");
  const auto model = key.substr(4, split - 4);
  // A composite interface (&MI_) is not the physical USB parent from baseline.
  need(model.size() == 17 || model.size() == 26, "PHYSICAL_DEVICE_ID_REQUIRED");
  need(model.substr(0, 4) == "VID_" && model.substr(8, 5) == "&PID_",
       "PHYSICAL_DEVICE_ID_REQUIRED");
  const auto hex4 = [&](std::size_t start) {
    return model.substr(start, 4).find_first_not_of("0123456789ABCDEF") ==
           std::string::npos;
  };
  need(hex4(4) && hex4(13), "PHYSICAL_DEVICE_ID_REQUIRED");
  if (model.size() == 26)
    need(model.substr(17, 5) == "&REV_" && hex4(22),
         "PHYSICAL_DEVICE_ID_REQUIRED");
  return id.substr(0, split);
}
Request parse_request(const std::string &payload, const std::string &expected) {
  need(hash(expected) && sha256(payload) == expected, "REQUEST_HASH");
  auto f = rocell::usb_identity::parse_flat(payload, request_limit);
  const std::set<std::string> keys = {"schema",
                                      "attempt_id",
                                      "session_id",
                                      "source_sha256",
                                      "phase_binding_sha256",
                                      "target_instance_id",
                                      "target_instance_id_sha256",
                                      "selected_identity_sha256",
                                      "operation_sha256",
                                      "permit_sha256",
                                      "helper_sha256",
                                      "runtime_registration_sha256",
                                      "request_nonce",
                                      "native_duration_ms",
                                      "admission_timeout_ms",
                                      "sample_count"};
  need(f.size() == keys.size(), "REQUEST_FIELDS");
  for (const auto &[key, value] : f) {
    need(keys.count(key) == 1, "REQUEST_FIELDS");
    const bool number = key == "sample_count" || key == "native_duration_ms" ||
                        key == "admission_timeout_ms";
    need(value.number == number, "REQUEST_FIELD_TYPE");
    if (key.find("sha256") != std::string::npos || key == "request_nonce")
      need(hash(value.text), "REQUEST_DIGEST");
  }
  need(f.at("schema").text == "rocell.native_usb_presence_request.v1",
       "REQUEST_SCHEMA");
  need(identifier(f.at("attempt_id").text) &&
           identifier(f.at("session_id").text),
       "REQUEST_ID");
  need(f.at("native_duration_ms").text == "2000" &&
           f.at("admission_timeout_ms").text == "5000" &&
           f.at("sample_count").text == "2",
       "FIXED_BUDGET_REQUIRED");
  const auto target = f.at("target_instance_id").text;
  need(sha256(target) == f.at("target_instance_id_sha256").text, "TARGET_HASH");
  return {std::move(f), payload, expected, target, device_filter(target)};
}
Observation observe(PresenceApi &api, const Request &r,
                    const std::string &origin,
                    const std::function<bool()> &cancelled,
                    const std::function<Moment()> &clock) {
  need(origin == "WINDOWS_CONFIGURATION_MANAGER" ||
           origin == "INCAPABLE_FIXTURE",
       "PROVIDER_ORIGIN");
  // Reconstruct the request before any API call, even if a caller mutated a
  // DTO.
  const auto request = parse_request(r.payload, r.hash);
  Observation out;
  out.request = request;
  out.origin = origin;
  out.start = clock();
  Moment previous = out.start;
  const auto check = [&]() {
    const auto now = clock();
    need(now.monotonic_ms >= previous.monotonic_ms &&
             now.utc_ns >= previous.utc_ns && now.utc_ns > 0,
         "CLOCK_REGRESSION");
    previous = now;
    need(!cancelled(), "CANCELLED");
    need(now.monotonic_ms - out.start.monotonic_ms < duration_ms,
         "ACQUISITION_DEADLINE");
    return now;
  };
  try {
    for (std::uint32_t index = 0; index < sample_count; ++index) {
      const auto start = check();
      out.samples.emplace_back();
      auto &sample = out.samples.back();
      sample.start = sample.finish = start;
      ++sample.api_calls;
      const auto size = api.size(request.filter);
      sample.native_code = size.code;
      sample.required_chars = size.required_chars;
      sample.finish = check();
      need(size.code == 0, "SIZE_API_FAILED");
      need(size.required_chars > 0 && size.required_chars <= max_chars,
           "LIST_SIZE_LIMIT");
      ++sample.api_calls;
      sample.native_code.reset();
      const auto listed = api.list(request.filter, size.required_chars);
      sample.native_code = listed.code;
      sample.finish = check();
      // Size/list races fail closed. Never treat ERROR/CR_BUFFER_SMALL as an
      // empty list.
      need(listed.code == 0, "LIST_API_FAILED");
      parse_list(sample, listed.multi_sz, request);
      sample.finish = check();
      sample.complete = true;
    }
    out.finish = check();
    const auto first = out.samples[0].target_present;
    if (first != out.samples[1].target_present) {
      out.error = "PRESENCE_CHANGED_DURING_ACQUISITION";
    } else {
      out.outcome = first ? "PRESENT" : "ABSENT";
    }
  } catch (const PresenceFailure &e) {
    out.error = e.what();
    if (!out.samples.empty() && !out.samples.back().complete)
      out.samples.back().error = out.error;
  } catch (...) {
    out.error = "API_EXCEPTION";
    if (!out.samples.empty() && !out.samples.back().complete)
      out.samples.back().error = out.error;
  }
  out.finish = clock();
  if (out.finish.monotonic_ms < previous.monotonic_ms ||
      out.finish.utc_ns < previous.utc_ns) {
    out.outcome = "HELD";
    out.error = "CLOCK_REGRESSION";
  }
  if (out.finish.monotonic_ms >= out.start.monotonic_ms &&
      out.finish.monotonic_ms - out.start.monotonic_ms >= duration_ms) {
    out.outcome = "HELD";
    out.error = "ACQUISITION_DEADLINE";
  }
  return out;
}
std::string serialize(const Observation &o) {
  std::string result =
      "{\"schema\":\"rocell.windows_usb_presence.v1\",\"request\":" +
      o.request.payload + ",\"request_sha256\":" + quote(o.request.hash) +
      ",\"provider\":" + quote(o.origin) +
      ",\"filter\":" + quote(o.request.filter) +
      ",\"scope\":\"PRESENT_PHYSICAL_USB_DEVICE_INSTANCES\"" +
      ",\"outcome\":" + quote(o.outcome) +
      ",\"error\":" + (o.error.empty() ? "null" : quote(o.error)) +
      ",\"started\":" + moment_json(o.start) +
      ",\"finished\":" + moment_json(o.finish) + ",\"samples\":[";
  std::uint32_t count = 0;
  for (std::size_t i = 0; i < o.samples.size(); ++i) {
    const auto &s = o.samples[i];
    if (i)
      result += ',';
    count += s.api_calls;
    result += "{\"started\":" + moment_json(s.start) +
              ",\"finished\":" + moment_json(s.finish) +
              ",\"required_chars\":" + std::to_string(s.required_chars) +
              ",\"used_chars\":" + std::to_string(s.used_chars) +
              ",\"api_calls\":" + std::to_string(s.api_calls) +
              ",\"native_code\":" +
              (s.native_code ? std::to_string(*s.native_code) : "null") +
              ",\"complete\":" + (s.complete ? "true" : "false") +
              ",\"target_present\":" +
              (s.complete ? (s.target_present ? "true" : "false") : "null") +
              ",\"error\":" + (s.error.empty() ? "null" : quote(s.error)) +
              ",\"instance_ids\":[";
    for (std::size_t j = 0; j < s.ids.size(); ++j) {
      if (j)
        result += ',';
      result += quote(s.ids[j]);
    }
    result += "]}";
  }
  result += "],\"api_calls\":" + std::to_string(count) +
            ",\"device_handle_opens\":0,\"configuration_writes\":0,\"frames\":"
            "0,\"physical_authority\":false}";
  need(result.size() <= output_limit, "OUTPUT_LIMIT");
  return result;
}
} // namespace rocell::usb_presence
