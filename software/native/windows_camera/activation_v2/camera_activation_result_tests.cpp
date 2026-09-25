// Synthetic native observations, actual owned pipe codec and result formatter.
// No Windows metadata adapter, COM/MF, camera or output-file implementation links.
#include <windows.h>

#include <iostream>
#include <sstream>

#include "camera_activation_entry.h"

namespace ae = rocell::activation_entry;
namespace ap = rocell::activation_protocol;
namespace ag = rocell::activation_gate;
namespace ai = rocell::activation_identity;
namespace id = rocell::identity;
namespace {
template <class T>
auto seen(T value) {
  return id::Observation<T>::observed_value(std::move(value));
}
std::string quote(const std::string& value) {
  std::string out = "\"";
  for (char c : value) {
    if (c == '"' || c == '\\') out += '\\';
    if (static_cast<unsigned char>(c) < 32) throw std::runtime_error("TEST_QUOTE_CONTROL");
    out += c;
  }
  return out + '"';
}
id::IdentityMetadata modeled(const ai::Expected& e) {
  id::IdentityMetadata out;
  out.requested_endpoint = e.endpoint;
  out.mapping.devnode = seen<id::DevNode>(7);
  out.mapping.interface_path = seen(e.endpoint);
  out.device =
      id::NodeMetadata{7, seen(e.instance_id), seen(e.container), seen(e.location_paths)};
  out.driver = id::DriverMetadata{7, seen(e.driver_provider), seen(e.driver_service),
                                  seen(e.driver_version), seen(e.driver_inf)};
  out.parents = {{1, seen<std::wstring>(L"HTREE\\MODELED_ROOT"), {}, {}}};
  out.observed_root = seen<id::DevNode>(1);
  out.chain_end = id::ChainEnd::ReachedObservedRoot;
  out.api_calls = 13;  // MODELED API-seam count, not an invocation of a device API.
  std::size_t bytes = 16 + 2;
  for (const auto& path : e.location_paths) bytes += path.size() * 2 + 2;
  for (const auto* field :
       {&e.driver_provider, &e.driver_service, &e.driver_version, &e.driver_inf})
    bytes += field->size() * 2 + 2;
  out.observed_property_bytes = static_cast<std::uint32_t>(bytes);
  return out;
}
std::string native_body(const ae::Admitted& admitted, bool opened, bool failed,
                        bool cleanup_failed) {
  const bool capture = admitted.purpose == ap::Purpose::Capture;
  const auto endpoint = quote(admitted.state.request().endpoint());
  const std::string mode =
      R"({"width":4,"height":2,"fps_numerator":9,"fps_denominator":1,"subtype":"YUY2","stride_bytes":8})";
  std::ostringstream out;
  out << R"({"schema":"rocell.windows_camera.v1","operation":)"
      << (capture ? "\"capture\"" : "\"probe\"") << R"(,"status":)"
      << (failed ? "\"FAILED\"" : "\"OK\"") << R"(,"reason_code":)"
      << (failed ? "\"MODELED_FAILURE\"" : "null") << R"(,"selected_endpoint":)" << endpoint
      << R"(,"devices":[{"symbolic_link":)" << endpoint
      << R"(,"friendly_name":"MODELED camera"}],"modes":)" << (opened ? "[" + mode + "]" : "[]")
      << R"(,"requested_mode":)" << (capture ? mode : "null") << R"(,"observed_mode":)"
      << (capture && opened ? mode : "null") << R"(,"controls":[],"frames":)";
  if (capture && opened)
    out << R"([{"filename":"frame-000000.yuy2","length_bytes":16,"stride_bytes":8,"row0_offset_bytes":0,"host_sequence":0,"media_timestamp_100ns":-200,"host_arrival_qpc":1234567,"qpc_frequency":10000000,"discontinuity":null}])";
  else
    out << "[]";
  out << R"(,"counts":{"source_activation_attempts":)" << opened << R"(,"source_opened":)"
      << opened << R"(,"control_set_attempts":0,"samples_received":)" << (capture && opened)
      << R"(,"frames_written":)" << (capture && opened) << R"(,"source_shutdown_attempts":)"
      << opened << R"(},"cleanup":{"source_shutdown_hr":)"
      << (opened ? (cleanup_failed ? "-1" : "0") : "null")
      << R"(,"source_released":true,"mf_shutdown_hr":0,"com_uninitialized":true},"limitations":["SENSOR_SEQUENCE_UNAVAILABLE","MEDIA_TIMESTAMP_IS_NOT_EXPOSURE_TIME"]})";
  return out.str();
}
}  // namespace

int wmain(int argc, wchar_t** argv) {
  try {
    if (argc != 5) throw std::runtime_error("RESULT_TEST_ARGUMENTS");
    const std::wstring operation = argv[1], scenario = argv[2];
    if (operation != L"--probe" && operation != L"--capture")
      throw std::runtime_error("RESULT_TEST_OPERATION");
    if (scenario != L"ok" && scenario != L"driver-changed" && scenario != L"query-threw" &&
        scenario != L"late-return" && scenario != L"not-started" &&
        scenario != L"cleanup-failed")
      throw std::runtime_error("RESULT_TEST_SCENARIO");
    const auto admitted =
        ae::admit({argv[3], argv[4]},
                  operation == L"--capture" ? ap::Purpose::Capture : ap::Purpose::Probe);
    ag::Gate gate;
    bool opened = false;
    std::uint64_t now = admitted.native_started_ms + 50;
    if (scenario != L"not-started") {
      try {
        gate.run(
            admitted.identity.traits, admitted.native_started_ms, admitted.native_deadline_ms,
            {[&]() { return now; }, []() { return false; }},
            [&](const id::Limits&, const id::RunControl&) {
              if (scenario == L"query-threw") throw std::runtime_error("MODELED_QUERY_THROW");
              auto observation = modeled(admitted.identity.traits);
              if (scenario == L"driver-changed")
                observation.driver->service = seen<std::wstring>(L"changed");
              now = scenario == L"late-return" ? admitted.native_deadline_ms : now + 10;
              return observation;
            },
            [&]() { opened = true; });  // In-memory ONLY, never an OS activation.
      } catch (const std::exception&) {
      }
    }
    const bool failed = !opened || scenario == L"cleanup-failed";
    std::cout << ae::wrap_result(
                     admitted, gate.record(),
                     native_body(admitted, opened, failed, scenario == L"cleanup-failed"))
              << '\n';
    return failed ? 1 : 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 2;
  }
}
