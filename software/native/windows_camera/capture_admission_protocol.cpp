#include "capture_admission_protocol.h"
#include <windows.h>
#include <algorithm>
#include <limits>
#include <set>
#include <stdexcept>

namespace rocell::capture_admission {
namespace {
using admission::Fields;
void need(bool value, const char* reason) { if (!value) throw std::runtime_error(reason); }
bool hexhash(const std::string& s) {
  return s.size() == 64 && std::all_of(s.begin(), s.end(), [](char c) {
    return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
  });
}
bool identifier(const std::string& s) {
  if (s.empty() || s.size() > 96) return false;
  for (std::size_t i = 0; i < s.size(); ++i) {
    const char c = s[i];
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) continue;
    if (i && (c == '_' || c == '.' || c == '-')) continue;
    return false;
  }
  return true;
}
void exact(const Fields& f, const std::set<std::string>& names) {
  need(f.size() == names.size(), "CAPTURE_FIELD_SET");
  for (const auto& [name, value] : f) { (void)value; need(names.count(name) == 1, "CAPTURE_UNKNOWN_FIELD"); }
}
std::string str(const Fields& f, const std::string& key) {
  const auto& value = f.at(key); need(!value.number, "CAPTURE_STRING_REQUIRED"); return value.text;
}
std::uint64_t number(const Fields& f, const std::string& key, std::uint64_t low, std::uint64_t high) {
  const auto& value = f.at(key); need(value.number, "CAPTURE_INTEGER_REQUIRED");
  const auto result = std::stoull(value.text);
  need(result >= low && result <= high, "CAPTURE_INTEGER_BOUNDS"); return result;
}
std::int64_t signed_decimal(const std::string& s, std::int64_t low, std::int64_t high) {
  need(!s.empty() && s.size() <= 11, "CAPTURE_SIGNED_DECIMAL");
  const std::size_t begin = s[0] == '-' ? 1 : 0;
  need(begin < s.size(), "CAPTURE_SIGNED_DECIMAL");
  need((s.size() - begin == 1 || s[begin] != '0') && s != "-0", "CAPTURE_SIGNED_DECIMAL");
  for (auto i = begin; i < s.size(); ++i) need(s[i] >= '0' && s[i] <= '9', "CAPTURE_SIGNED_DECIMAL");
  const auto value = std::stoll(s); need(value >= low && value <= high, "CAPTURE_SIGNED_BOUNDS"); return value;
}
std::wstring wide(const std::string& s) {
  need(!s.empty() && s.size() <= 4096, "CAPTURE_TEXT_BOUNDS");
  const int count = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), nullptr, 0);
  need(count > 0, "CAPTURE_UTF8_INVALID");
  std::wstring result(static_cast<std::size_t>(count), L'\0');
  need(MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(), static_cast<int>(s.size()), result.data(), count) == count, "CAPTURE_UTF8_FAILED");
  return result;
}
void local_path(const std::string& s) {
  need(s.size() > 3 && s.size() <= 4096 &&
       ((s[0] >= 'A' && s[0] <= 'Z') || (s[0] >= 'a' && s[0] <= 'z')) &&
       s[1] == ':' && s[2] == '\\' && s.back() != '\\', "CAPTURE_LOCAL_PATH_REQUIRED");
  // No normalization: alternate separators, ADS, dot components, Win32 device
  // aliases and trailing-dot/space forms must not retarget a bound path.
  std::size_t start = 3;
  for (std::size_t i = 3; i <= s.size(); ++i) {
    if (i < s.size() && s[i] != '\\') {
      const auto c = static_cast<unsigned char>(s[i]);
      need(c >= 32 && c != 127 && s[i] != ':' && s[i] != '/' && s[i] != '*' &&
           s[i] != '?' && s[i] != '"' && s[i] != '<' && s[i] != '>' && s[i] != '|', "CAPTURE_PATH_CHARACTER");
      continue;
    }
    const auto part = s.substr(start, i - start);
    need(!part.empty() && part != "." && part != ".." && part.back() != '.' && part.back() != ' ', "CAPTURE_PATH_COMPONENT");
    auto stem = part.substr(0, part.find('.'));
    for (auto& c : stem) if (c >= 'a' && c <= 'z') c = static_cast<char>(c - 'a' + 'A');
    need(stem != "CON" && stem != "PRN" && stem != "AUX" && stem != "NUL" &&
      !(stem.size() == 4 && (stem.substr(0, 3) == "COM" || stem.substr(0, 3) == "LPT") && stem[3] >= '1' && stem[3] <= '9'), "CAPTURE_PATH_DEVICE_ALIAS");
    start = i + 1;
  }
  (void)wide(s);
}
void validate_controls(const std::string& text) {
  need(text.size() <= 512, "CAPTURE_CONTROL_LIMIT");
  if (text.empty()) return;
  const std::set<std::string> allowed{"brightness", "contrast", "exposure", "gain", "saturation", "white_balance"};
  std::string previous; std::size_t start = 0, count = 0;
  while (start < text.size()) {
    const auto end = text.find(';', start);
    const auto part = text.substr(start, end == std::string::npos ? std::string::npos : end - start);
    const auto a = part.find(','), b = part.find(',', a == std::string::npos ? 0 : a + 1);
    need(a != std::string::npos && b != std::string::npos && part.find(',', b + 1) == std::string::npos, "CAPTURE_CONTROL_ENCODING");
    const auto id = part.substr(0, a), mode = part.substr(b + 1);
    need(allowed.count(id) == 1 && id > previous && ++count <= 6, "CAPTURE_CONTROL_ID_ORDER");
    previous = id;
    (void)signed_decimal(part.substr(a + 1, b - a - 1), -2147483648LL, 2147483647LL);
    need(mode == "auto" || mode == "manual", "CAPTURE_CONTROL_MODE");
    if (end == std::string::npos) break;
    start = end + 1; need(start < text.size(), "CAPTURE_CONTROL_TRAILING");
  }
}
}

CaptureSettings parse_capture_settings(const std::string& payload) {
  auto f = admission::parse_flat(payload, admission::request_limit);
  exact(f, {"width", "height", "fps_numerator", "fps_denominator", "subtype", "frame_count", "max_frame_bytes", "max_total_bytes", "output_directory", "controls", "requested_stride_bytes"});
  CaptureSettings result;
  result.width = static_cast<std::uint32_t>(number(f, "width", 2, 16384));
  result.height = static_cast<std::uint32_t>(number(f, "height", 1, 16384));
  result.fps_numerator = static_cast<std::uint32_t>(number(f, "fps_numerator", 1, 1000000));
  result.fps_denominator = static_cast<std::uint32_t>(number(f, "fps_denominator", 1, 1000000));
  result.frame_count = static_cast<std::uint32_t>(number(f, "frame_count", 1, 32));
  result.max_frame_bytes = number(f, "max_frame_bytes", 1, 64ULL * 1024 * 1024);
  result.max_total_bytes = number(f, "max_total_bytes", result.max_frame_bytes, 2ULL * 1024 * 1024 * 1024);
  need(str(f, "subtype") == "YUY2" && result.width % 2 == 0 &&
    std::uint64_t(result.width) * result.height * 2 <= result.max_frame_bytes, "CAPTURE_FORMAT_BOUNDS");
  const auto stride = str(f, "requested_stride_bytes");
  if (!stride.empty()) {
    const auto value = signed_decimal(stride, -1048576, 1048576);
    need(value != 0, "CAPTURE_ZERO_STRIDE");
    const auto magnitude = static_cast<std::uint64_t>(value < 0 ? -value : value);
    need(magnitude >= std::uint64_t(result.width) * 2 &&
      std::uint64_t(result.height - 1) * magnitude + std::uint64_t(result.width) * 2 <= result.max_frame_bytes,
      "CAPTURE_STRIDE_BUDGET");
    result.requested_stride = static_cast<std::int32_t>(value);
  }
  result.output_directory = str(f, "output_directory"); local_path(result.output_directory);
  result.controls = str(f, "controls"); validate_controls(result.controls);
  result.fields = std::move(f); return result;
}
admission::Request parse_request(const std::string& payload, const std::string& expected_hash) {
  need(hexhash(expected_hash) && admission::sha256(payload) == expected_hash, "CAPTURE_REQUEST_HASH");
  auto f = admission::parse_flat(payload, admission::request_limit);
  exact(f, {"schema", "attempt_id", "session_id", "source_sha256", "operation_sha256", "selected_identity_sha256", "endpoint", "endpoint_sha256", "helper_sha256", "runtime_registration_sha256", "camera_request_sha256", "permit_sha256", "native_duration_ms", "admission_timeout_ms", "capture_json"});
  need(str(f, "schema") == "rocell.native_camera_capture_admission_request.v1", "CAPTURE_REQUEST_SCHEMA");
  need(identifier(str(f, "attempt_id")) && identifier(str(f, "session_id")), "CAPTURE_REQUEST_ID");
  for (const auto& key : {"source_sha256", "operation_sha256", "selected_identity_sha256", "endpoint_sha256", "helper_sha256", "runtime_registration_sha256", "camera_request_sha256", "permit_sha256"}) need(hexhash(str(f, key)), "CAPTURE_REQUEST_DIGEST");
  const auto endpoint = str(f, "endpoint");
  need(!endpoint.empty() && endpoint.size() <= 4096 && admission::sha256(endpoint) == str(f, "endpoint_sha256"), "CAPTURE_ENDPOINT_BINDING");
  need(number(f, "native_duration_ms", native_duration_ms, native_duration_ms) == native_duration_ms &&
    number(f, "admission_timeout_ms", admission_timeout_ms, admission_timeout_ms) == admission_timeout_ms, "CAPTURE_BUDGET");
  const auto capture = parse_capture_settings(str(f, "capture_json"));
  need(capture.output_directory.substr(capture.output_directory.find_last_of('\\') + 1)
    == "capture-" + str(f, "attempt_id"), "CAPTURE_ASSIGNED_LEAF");
  return {std::move(f), expected_hash};
}
std::vector<std::wstring> capture_arguments(const admission::AdmissionState& state, const std::wstring& cwd) {
  need(state.admitted(), "CAPTURE_ADMISSION_REQUIRED");
  const auto& request = state.request();
  need(str(request.fields, "schema") == "rocell.native_camera_capture_admission_request.v1", "CAPTURE_REQUEST_SCHEMA");
  const auto settings = parse_capture_settings(str(request.fields, "capture_json"));
  const auto output = wide(settings.output_directory);
  need(!cwd.empty() && cwd.back() != L'\\' &&
    output == cwd + L"\\capture-" + wide(str(request.fields, "attempt_id")), "CAPTURE_PRIVATE_DIRECTORY_BINDING");
  std::vector<std::wstring> result{L"capture", L"--endpoint", wide(request.endpoint()), L"--max-ms", L"5000",
    L"--width", std::to_wstring(settings.width), L"--height", std::to_wstring(settings.height),
    L"--fps-n", std::to_wstring(settings.fps_numerator), L"--fps-d", std::to_wstring(settings.fps_denominator),
    L"--frames", std::to_wstring(settings.frame_count), L"--frame-bytes", std::to_wstring(settings.max_frame_bytes),
    L"--total-bytes", std::to_wstring(settings.max_total_bytes), L"--output", output};
  if (!settings.controls.empty()) { result.push_back(L"--controls"); result.push_back(wide(settings.controls)); }
  return result;
}
}
