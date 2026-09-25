// Canonical data/handshake tests only; no camera worker or metadata resolver.
#include <functional>
#include <iostream>
#include <stdexcept>

#include "camera_activation_protocol.h"
#include "capture_admission_protocol.h"

namespace ap = rocell::activation_protocol;
namespace ad = rocell::admission;
namespace {
unsigned checks = 0;
void check(bool condition) {
  ++checks;
  if (!condition) throw std::runtime_error("ACTIVATION_PROTOCOL_TEST_FAILED");
}
void denied(const std::function<void()>& action) {
  bool refused = false;
  try {
    action();
  } catch (const std::exception&) {
    refused = true;
  }
  check(refused);
}
std::string quote(const std::string& value) {
  std::string result = "\"";
  for (char c : value) {
    if (c == '"' || c == '\\') result += '\\';
    result += c;
  }
  return result + '"';
}
std::string json(const ad::Fields& fields) {
  std::string result = "{";
  for (const auto& [key, value] : fields) {
    if (result.size() > 1) result += ',';
    result += quote(key) + ':' + (value.number ? value.text : quote(value.text));
  }
  return result + '}';
}
ad::Fields expectation() {
  return {{"schema", {"rocell.camera_activation_identity_expectation.v1"}},
          {"original_identity_sha256", {std::string(64, 'b')}},
          {"endpoint", {"opaque-camera-endpoint"}},
          {"instance_id", {"USB\\UNIT_1"}},
          {"container_id", {"00000001-0002-0003-0405-060708090a0b"}},
          {"location_paths_json",
           {json({{"path_00", {"PCIROOT(0)#USB(1)"}}, {"path_01", {"ACPI(1)#USB(1)"}}})}},
          {"driver_provider", {"Microsoft"}},
          {"driver_service", {"usbvideo"}},
          {"driver_version", {"10.0.1.2"}},
          {"driver_inf", {"usbvideo.inf"}}};
}
ad::Fields capture_settings() {
  return {{"width", {"5472", true}},
          {"height", {"3648", true}},
          {"fps_numerator", {"9", true}},
          {"fps_denominator", {"1", true}},
          {"subtype", {"YUY2"}},
          {"frame_count", {"1", true}},
          {"max_frame_bytes", {"39923712", true}},
          {"max_total_bytes", {"39923712", true}},
          {"output_directory", {"C:\\incapable\\capture-attempt-1"}},
          {"controls", {""}},
          {"requested_stride_bytes", {""}}};
}
ad::Fields request(bool capture) {
  ad::Fields fields{{"schema",
                     {capture ? "rocell.native_camera_capture_admission_request.v2"
                              : "rocell.native_camera_admission_request.v2"}},
                    {"attempt_id", {"attempt-1"}},
                    {"session_id", {"session-1"}},
                    {"endpoint", {"opaque-camera-endpoint"}},
                    {"native_duration_ms", {"5000", true}},
                    {"admission_timeout_ms", {capture ? "5000" : "2000", true}},
                    {"activation_identity_json", {json(expectation())}}};
  for (const auto* key :
       {"source_sha256", "operation_sha256", "selected_identity_sha256", "helper_sha256",
        "runtime_registration_sha256", "camera_request_sha256", "permit_sha256"})
    fields[key] = {std::string(64, 'a')};
  fields["endpoint_sha256"] = {ad::sha256(fields.at("endpoint").text)};
  if (capture) fields["capture_json"] = {json(capture_settings())};
  return fields;
}
ap::Request parse(const ad::Fields& fields, bool capture) {
  const auto wire = json(fields);
  return ap::parse_request(wire, ad::sha256(wire),
                           capture ? ap::Purpose::Capture : ap::Purpose::Probe);
}
}  // namespace

int main(int argc, char** argv) {
  try {
    if (argc != 1) {
      // Explicit parser-only interop lane in this incapable test executable.
      // The test parent supplies EOF and a process timeout; no camera worker,
      // metadata resolver, arbitrary command or file path is accepted here.
      if (argc != 2) throw std::runtime_error("PARSER_TEST_ARGUMENTS");
      const std::string action = argv[1];
      if (action != "--parse-expectation" && action != "--parse-probe")
        throw std::runtime_error("PARSER_TEST_ARGUMENTS");
      std::string payload;
      char next = 0;
      while (std::cin.get(next)) {
        if (payload.size() >= 16383) throw std::runtime_error("PARSER_TEST_BYTE_LIMIT");
        payload += next;
      }
      const auto parsed =
          action == "--parse-expectation"
              ? ap::parse_expected_identity(payload)
              : ap::parse_request(payload, ad::sha256(payload), ap::Purpose::Probe).identity;
      std::cout << "{\"device_calls\":0,\"expectation_sha256\":\"" << parsed.payload_sha256
                << "\",\"original_identity_sha256\":\"" << parsed.original_identity_sha256
                << "\",\"input_sha256\":\"" << ad::sha256(payload) << "\"}\n";
      return 0;
    }
    const auto pin = ap::parse_expected_identity(json(expectation()));
    check(pin.traits.endpoint == L"opaque-camera-endpoint");
    check(pin.traits.instance_id == L"USB\\UNIT_1");
    check(pin.traits.container.data1 == 1 && pin.traits.container.data2 == 2 &&
          pin.traits.container.data3 == 3);
    check(pin.traits.container.data4 == std::array<std::uint8_t, 8>{4, 5, 6, 7, 8, 9, 10, 11});
    check(pin.traits.location_paths.size() == 2 &&
          pin.traits.location_paths[1] == L"ACPI(1)#USB(1)");
    for (const bool capture : {false, true}) {
      const auto fields = request(capture);
      const auto wire = json(fields);
      const auto parsed = parse(fields, capture);
      check(parsed.admission.hash == ad::sha256(wire));
      check(parsed.identity.payload_sha256 ==
            ad::sha256(fields.at("activation_identity_json").text));
      check(parsed.identity.original_identity_sha256 == std::string(64, 'b'));
      check(parsed.admission.fields.size() == (capture ? 16 : 15));
      denied([&] { (void)parse(fields, !capture); });
      denied([&] { (void)ad::parse_request(wire, ad::sha256(wire)); });
      denied([&] { (void)rocell::capture_admission::parse_request(wire, ad::sha256(wire)); });
      for (const auto& [key, value] : fields) {
        (void)value;
        auto changed = fields;
        changed.erase(key);
        denied([&] { (void)parse(changed, capture); });
      }
      auto changed = fields;
      changed["extra"] = {"not allowed"};
      denied([&] { (void)parse(changed, capture); });
      changed = fields;
      changed["schema"].text.back() = '1';
      denied([&] { (void)parse(changed, capture); });
      changed = fields;
      changed["native_duration_ms"] = {"6000", true};
      denied([&] { (void)parse(changed, capture); });
      changed = fields;
      changed["admission_timeout_ms"] = {capture ? "2000" : "5000", true};
      denied([&] { (void)parse(changed, capture); });
      changed = fields;
      changed["selected_identity_sha256"] = {std::string(64, '0')};
      denied([&] { (void)parse(changed, capture); });
      changed = fields;
      changed["activation_identity_json"].text += ' ';
      denied([&] { (void)parse(changed, capture); });
      auto other = expectation();
      other["endpoint"] = {"other-endpoint"};
      changed = fields;
      changed["activation_identity_json"] = {json(other)};
      denied([&] { (void)parse(changed, capture); });
      denied([&] { (void)ap::parse_request(wire, std::string(64, 'c'), parsed.purpose); });
      denied(
          [&] { (void)ap::parse_request(wire + ' ', ad::sha256(wire + ' '), parsed.purpose); });
      denied([&] {
        (void)ap::parse_request(std::string(16384, 'x'), ad::sha256(std::string(16384, 'x')),
                                parsed.purpose);
      });

      // The existing READY/RELEASE state binds the COMPLETE new request hash.
      // Reusing that hash-bound envelope does not submit a shortened v1 request.
      const auto challenge = std::string(64, 'd');
      ad::AdmissionState state(parsed.admission, 123, challenge);
      check(state.ready().find(parsed.admission.hash) != std::string::npos);
      ad::Fields release{{"schema", {"rocell.native_camera_admission_release.v1"}},
                         {"request_sha256", {parsed.admission.hash}},
                         {"child_pid", {"123", true}},
                         {"challenge_sha256", {ad::sha256(challenge)}},
                         {"permit_sha256", {parsed.admission.permit()}}};
      state.accept(json(release), true);
      check(state.admitted());
      denied([&] { state.accept(json(release), true); });
      auto revised = fields;
      auto replacement = expectation();
      replacement["driver_version"] = {"new-driver"};
      revised["activation_identity_json"] = {json(replacement)};
      ad::AdmissionState replacement_state(parse(revised, capture).admission, 123, challenge);
      denied([&] { replacement_state.accept(json(release), true); });
      check(!replacement_state.admitted());
    }
    auto bad_capture = request(true);
    auto settings = capture_settings();
    settings["output_directory"] = {"C:\\incapable\\wrong-attempt"};
    bad_capture["capture_json"] = {json(settings)};
    denied([&] { (void)parse(bad_capture, true); });
    for (const auto& [key, value] : expectation()) {
      (void)value;
      auto missing = expectation();
      missing.erase(key);
      denied([&] { (void)ap::parse_expected_identity(json(missing)); });
    }
    for (const auto& paths : {ad::Fields{{"path_01", {"wrong first"}}},
                              ad::Fields{{"path_00", {"same"}}, {"path_01", {"same"}}},
                              ad::Fields{{"path_00", {"1", true}}}}) {
      auto invalid = expectation();
      invalid["location_paths_json"] = {json(paths)};
      denied([&] { (void)ap::parse_expected_identity(json(invalid)); });
    }
    for (const auto& guid : {"00000000-0000-0000-0000-000000000000",
                             "00000001-0002-0003-0405-060708090A0B", "not-a-guid"}) {
      auto invalid = expectation();
      invalid["container_id"] = {guid};
      denied([&] { (void)ap::parse_expected_identity(json(invalid)); });
    }
    auto unicode = json(expectation());
    const auto at = unicode.find("Microsoft");
    check(at != std::string::npos);
    unicode.replace(at, 9, "M\\u00e9ta\\ud83d\\udcf7");
    const auto parsed_unicode = ap::parse_expected_identity(unicode);
    check(parsed_unicode.traits.driver_provider == L"M\u00e9ta\U0001f4f7");
    std::cout << checks << " incapable activation-protocol assertions passed; device calls=0\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << "; assertion=" << checks << '\n';
    return 1;
  }
}
