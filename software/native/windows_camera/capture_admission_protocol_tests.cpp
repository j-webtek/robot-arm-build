#include "capture_admission_protocol.h"
#include <iostream>
#include <stdexcept>

using rocell::admission::Fields;
using rocell::admission::sha256;
namespace capture = rocell::capture_admission;
namespace {
unsigned checks = 0;
void check(bool value) { ++checks; if (!value) throw std::runtime_error("ASSERTION_FAILED"); }
template<class F> void denied(F operation) { bool rejected = false; try { operation(); } catch (const std::exception&) { rejected = true; } check(rejected); }
std::string quote(const std::string& text) {
  std::string out = "\"";
  for (char c : text) { if (c == '\\' || c == '"') out += '\\'; out += c; }
  return out + '"';
}
std::string json(const Fields& fields) {
  std::string out = "{";
  for (const auto& [key, value] : fields) {
    if (out.size() > 1) out += ',';
    out += quote(key) + ':' + (value.number ? value.text : quote(value.text));
  }
  return out + '}';
}
Fields settings() {
  return {{"controls", {"", false}}, {"fps_denominator", {"1", true}}, {"fps_numerator", {"9", true}},
    {"frame_count", {"1", true}}, {"height", {"3648", true}}, {"max_frame_bytes", {"39923712", true}},
    {"max_total_bytes", {"39923712", true}}, {"output_directory", {"C:\\assigned\\capture-attempt-1", false}},
    {"requested_stride_bytes", {"10944", false}}, {"subtype", {"YUY2", false}}, {"width", {"5472", true}}};
}
Fields outer(const Fields& inner) {
  const std::string h(64, 'a'), endpoint = "incapable-fixture-only";
  return {{"admission_timeout_ms", {"5000", true}}, {"attempt_id", {"attempt-1", false}},
    {"camera_request_sha256", {h, false}}, {"capture_json", {json(inner), false}}, {"endpoint", {endpoint, false}},
    {"endpoint_sha256", {sha256(endpoint), false}}, {"helper_sha256", {h, false}}, {"native_duration_ms", {"5000", true}},
    {"operation_sha256", {h, false}}, {"permit_sha256", {h, false}}, {"runtime_registration_sha256", {h, false}},
    {"schema", {"rocell.native_camera_capture_admission_request.v1", false}}, {"selected_identity_sha256", {h, false}},
    {"session_id", {"session-1", false}}, {"source_sha256", {h, false}}};
}
rocell::admission::Request parsed(const Fields& fields) { const auto wire = json(fields); return capture::parse_request(wire, sha256(wire)); }
std::string release(const rocell::admission::Request& request, const std::string& challenge) {
  return json({{"challenge_sha256", {sha256(challenge), false}}, {"child_pid", {"123", true}},
    {"permit_sha256", {request.permit(), false}}, {"request_sha256", {request.hash, false}},
    {"schema", {"rocell.native_camera_admission_release.v1", false}}});
}
}
int main() {
  try {
    const auto original = settings(); const auto request = parsed(outer(original));
    const auto values = capture::parse_capture_settings(json(original));
    check(values.width == 5472 && values.height == 3648 && values.requested_stride == 10944);
    check(values.frame_count == 1 && values.max_total_bytes == 39923712 && values.controls.empty());
    const std::string challenge(64, 'b');
    rocell::admission::AdmissionState state(request, 123, challenge);
    denied([&] { capture::capture_arguments(state, L"C:\\assigned"); });
    state.accept(release(request, challenge), true);
    const auto args = capture::capture_arguments(state, L"C:\\assigned");
    check(args.size() == 21 && args[0] == L"capture" && args.back() == L"C:\\assigned\\capture-attempt-1");
    denied([&] { capture::capture_arguments(state, L"C:\\other"); });
    denied([&] { state.accept(release(request, challenge), true); });
    const auto wire = json(outer(original));
    denied([&] { rocell::admission::parse_request(wire, sha256(wire)); });
    denied([&] { capture::parse_request(wire, std::string(64, '0')); });
    auto probe = outer(original); probe.erase("capture_json");
    probe["schema"].text = "rocell.native_camera_admission_request.v1"; probe["admission_timeout_ms"].text = "2000";
    check(rocell::admission::parse_request(json(probe), sha256(json(probe))).fields.size() == 14);
    denied([&] { parsed(probe); });
    for (const auto& key : {"schema", "attempt_id", "endpoint", "endpoint_sha256", "helper_sha256", "permit_sha256", "capture_json"}) {
      auto bad = outer(original); bad[key].text = ""; denied([&] { parsed(bad); });
    }
    for (const auto& key : {"admission_timeout_ms", "native_duration_ms"}) {
      auto bad = outer(original); bad[key].text = "2000"; denied([&] { parsed(bad); });
    }
    auto missing = outer(original); missing.erase("source_sha256"); denied([&] { parsed(missing); });
    auto extra = outer(original); extra["raw_command"] = {"capture", false}; denied([&] { parsed(extra); });
    for (const auto& key : {"width", "height", "fps_numerator", "fps_denominator", "frame_count", "max_frame_bytes", "max_total_bytes"}) {
      auto bad = original; bad[key] = {"0", true}; denied([&] { parsed(outer(bad)); });
      bad = original; bad[key].number = false; denied([&] { parsed(outer(bad)); });
    }
    for (const auto& [key, value] : Fields{{"width", {"5473", true}}, {"height", {"16385", true}},
      {"fps_numerator", {"1000001", true}}, {"frame_count", {"33", true}}, {"max_frame_bytes", {"67108865", true}},
      {"max_total_bytes", {"2147483649", true}}, {"subtype", {"MJPG", false}}}) {
      auto bad = original; bad[key] = value; denied([&] { parsed(outer(bad)); });
    }
    for (const auto& text : {"0", "-0", "+1", "01", "-01", "1048577", "-1048577", "1.0", " 1", "1", "-1", "10943", "10948"}) {
      auto bad = original; bad["requested_stride_bytes"].text = text; denied([&] { parsed(outer(bad)); });
    }
    for (const auto& text : {"", "-10944"}) {
      auto good = original; good["requested_stride_bytes"].text = text; (void)parsed(outer(good)); ++checks;
    }
    for (const auto& text : {"1048576", "-1048576"}) {
      auto good = original; good["height"].text = "1"; good["requested_stride_bytes"].text = text;
      (void)parsed(outer(good)); ++checks;
    }
    for (const auto& text : {"C:\\", "\\\\server\\share\\a", "C:\\assigned\\..\\a", "C:\\assigned\\.\\a", "C:\\assigned\\a:stream", "C:/assigned/a", "C:\\assigned\\a.", "C:\\assigned\\a ", "C:\\assigned\\CON", "C:\\assigned\\NUL.txt", "C:\\assigned\\COM1", "C:\\assigned\\\\a"}) {
      auto bad = original; bad["output_directory"].text = text; denied([&] { parsed(outer(bad)); });
    }
    for (const auto& text : {"gain,1,manual;brightness,2,manual", "gain,1,manual;gain,2,manual", "focus,1,manual", "gain,1,3", "gain,+1,manual", "gain,01,manual", "gain,2147483648,manual", "gain,-2147483649,manual", "gain,1,manual;"}) {
      auto bad = original; bad["controls"].text = text; denied([&] { parsed(outer(bad)); });
    }
    auto good = original; good["controls"].text = "brightness,-2147483648,manual;contrast,0,auto;exposure,-1,manual;gain,2147483647,manual;saturation,2,manual;white_balance,3,manual";
    (void)parsed(outer(good)); ++checks;
    auto bad_inner = original; bad_inner["unknown"] = {"x", false}; denied([&] { parsed(outer(bad_inner)); });
    denied([&] { capture::parse_capture_settings(json(original) + "\n"); });
    denied([&] { capture::parse_request(std::string(16384, 'x'), sha256(std::string(16384, 'x'))); });
    std::cout << "incapable capture parser assertions=" << checks << "; device APIs linked=0\n";
    return 0;
  } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 1; }
}
