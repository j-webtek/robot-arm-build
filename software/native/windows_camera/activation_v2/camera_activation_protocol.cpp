#include "camera_activation_protocol.h"

#include <windows.h>

#include <algorithm>
#include <set>
#include <stdexcept>

#include "capture_admission_protocol.h"

namespace rocell::activation_protocol {
namespace {
using admission::Fields;
void need(bool condition, const char* reason) {
  if (!condition) throw std::runtime_error(reason);
}
bool digest(const std::string& value) {
  return value.size() == 64 && value != std::string(64, '0') &&
         std::all_of(value.begin(), value.end(),
                     [](char c) { return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'); });
}
void exact(const Fields& fields, const std::set<std::string>& names) {
  need(fields.size() == names.size(), "ACTIVATION_FIELD_SET");
  for (const auto& field : fields)
    need(names.count(field.first) == 1, "ACTIVATION_UNKNOWN_FIELD");
}
const std::string& text(const Fields& fields, const char* key) {
  const auto& value = fields.at(key);
  need(!value.number, "ACTIVATION_STRING_REQUIRED");
  return value.text;
}
bool identifier(const std::string& value) {
  if (value.empty() || value.size() > 96) return false;
  for (std::size_t i = 0; i < value.size(); ++i) {
    const char c = value[i];
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) continue;
    if (i && (c == '_' || c == '.' || c == '-')) continue;
    return false;
  }
  return true;
}
std::wstring wide(const std::string& value) {
  need(!value.empty() && value.size() <= 4096, "ACTIVATION_TEXT_BYTE_LIMIT");
  const int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                                        static_cast<int>(value.size()), nullptr, 0);
  need(count > 0, "ACTIVATION_UTF8_INVALID");
  std::wstring result(static_cast<std::size_t>(count), L'\0');
  need(MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                           static_cast<int>(value.size()), result.data(), count) == count,
       "ACTIVATION_UTF8_FAILED");
  return result;
}
identity::ContainerGuid container(const std::string& value) {
  need(value.size() == 36, "ACTIVATION_CONTAINER_FORMAT");
  for (std::size_t i = 0; i < value.size(); ++i) {
    const char c = value[i];
    need(i == 8 || i == 13 || i == 18 || i == 23
             ? c == '-'
             : ((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f')),
         "ACTIVATION_CONTAINER_FORMAT");
  }
  identity::ContainerGuid result;
  result.data1 = static_cast<std::uint32_t>(std::stoul(value.substr(0, 8), nullptr, 16));
  result.data2 = static_cast<std::uint16_t>(std::stoul(value.substr(9, 4), nullptr, 16));
  result.data3 = static_cast<std::uint16_t>(std::stoul(value.substr(14, 4), nullptr, 16));
  const std::size_t offsets[] = {19, 21, 24, 26, 28, 30, 32, 34};
  for (std::size_t i = 0; i < 8; ++i)
    result.data4[i] =
        static_cast<std::uint8_t>(std::stoul(value.substr(offsets[i], 2), nullptr, 16));
  return result;
}
}  // namespace

ExpectedIdentity parse_expected_identity(const std::string& payload) {
  // Use the existing strict canonical flat parser and its unchanged byte/field
  // caps. Indexed path keys preserve exact observed order without delimiter
  // guessing, string normalization or a second general-purpose JSON parser.
  const auto fields = admission::parse_flat(payload, admission::request_limit);
  exact(fields, {"schema", "original_identity_sha256", "endpoint", "instance_id",
                 "container_id", "location_paths_json", "driver_provider", "driver_service",
                 "driver_version", "driver_inf"});
  need(text(fields, "schema") == "rocell.camera_activation_identity_expectation.v1",
       "ACTIVATION_EXPECTATION_SCHEMA");
  ExpectedIdentity result;
  result.original_identity_sha256 = text(fields, "original_identity_sha256");
  need(digest(result.original_identity_sha256), "ACTIVATION_ORIGINAL_IDENTITY_HASH");
  auto& expected = result.traits;
  expected.endpoint = wide(text(fields, "endpoint"));
  expected.instance_id = wide(text(fields, "instance_id"));
  expected.container = container(text(fields, "container_id"));
  expected.driver_provider = wide(text(fields, "driver_provider"));
  expected.driver_service = wide(text(fields, "driver_service"));
  expected.driver_version = wide(text(fields, "driver_version"));
  expected.driver_inf = wide(text(fields, "driver_inf"));
  const auto paths =
      admission::parse_flat(text(fields, "location_paths_json"), admission::request_limit);
  need(!paths.empty() && paths.size() <= 16, "ACTIVATION_LOCATION_COUNT");
  unsigned index = 0;
  for (const auto& path : paths) {
    const auto key = std::string("path_") + (index < 10 ? "0" : "") + std::to_string(index);
    need(path.first == key && !path.second.number, "ACTIVATION_LOCATION_ORDER");
    expected.location_paths.push_back(wide(path.second.text));
    ++index;
  }
  need(activation_identity::expectation_valid(expected), "ACTIVATION_EXPECTATION_BOUNDS");
  result.payload_sha256 = admission::sha256(payload);
  return result;
}

Request parse_request(const std::string& payload, const std::string& expected_hash,
                      Purpose purpose) {
  need(purpose == Purpose::Probe || purpose == Purpose::Capture, "ACTIVATION_PURPOSE");
  need(digest(expected_hash) && admission::sha256(payload) == expected_hash,
       "ACTIVATION_REQUEST_HASH");
  auto fields = admission::parse_flat(payload, admission::request_limit);
  std::set<std::string> names{"schema",
                              "attempt_id",
                              "session_id",
                              "source_sha256",
                              "operation_sha256",
                              "selected_identity_sha256",
                              "endpoint",
                              "endpoint_sha256",
                              "helper_sha256",
                              "runtime_registration_sha256",
                              "camera_request_sha256",
                              "permit_sha256",
                              "native_duration_ms",
                              "admission_timeout_ms",
                              "activation_identity_json"};
  const bool capture = purpose == Purpose::Capture;
  if (capture) names.insert("capture_json");
  exact(fields, names);
  need(text(fields, "schema") == (capture ? "rocell.native_camera_capture_admission_request.v2"
                                          : "rocell.native_camera_admission_request.v2"),
       "ACTIVATION_REQUEST_SCHEMA");
  need(identifier(text(fields, "attempt_id")) && identifier(text(fields, "session_id")),
       "ACTIVATION_REQUEST_ID");
  for (const auto* key : {"source_sha256", "operation_sha256", "selected_identity_sha256",
                          "endpoint_sha256", "helper_sha256", "runtime_registration_sha256",
                          "camera_request_sha256", "permit_sha256"})
    need(digest(text(fields, key)), "ACTIVATION_REQUEST_DIGEST");
  const auto& endpoint = text(fields, "endpoint");
  need(!endpoint.empty() && endpoint.size() <= 4096 &&
           admission::sha256(endpoint) == text(fields, "endpoint_sha256"),
       "ACTIVATION_ENDPOINT_BINDING");
  need(fields.at("native_duration_ms").number &&
           fields.at("native_duration_ms").text == "5000" &&
           fields.at("admission_timeout_ms").number &&
           fields.at("admission_timeout_ms").text == (capture ? "5000" : "2000"),
       "ACTIVATION_BUDGET");
  auto expected = parse_expected_identity(text(fields, "activation_identity_json"));
  need(expected.traits.endpoint == wide(endpoint), "ACTIVATION_EXPECTED_ENDPOINT_CHANGED");
  if (capture) {
    // Reuse only the unchanged settings DATA validator. Never reconstruct or
    // submit a shortened v1 admission request or a different request hash.
    const auto settings =
        capture_admission::parse_capture_settings(text(fields, "capture_json"));
    need(settings.output_directory.substr(settings.output_directory.find_last_of('\\') + 1) ==
             "capture-" + text(fields, "attempt_id"),
         "ACTIVATION_CAPTURE_ASSIGNED_LEAF");
  }
  return {{std::move(fields), expected_hash}, std::move(expected), purpose};
}
}  // namespace rocell::activation_protocol
