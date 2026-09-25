#include "fixture_api.h"
#include <iostream>
#include <stdexcept>

using namespace rocell::usb_presence;
namespace {
std::uint32_t assertions = 0;
void expect(bool condition) {
  ++assertions;
  if (!condition)
    throw std::runtime_error("TEST_ASSERTION");
}
std::string
input(const std::string &target = "USB\\VID_1234&PID_5678\\UNIT_A") {
  // Sorted canonical fields, matching Python's request codec exactly.
  const std::string h(64, 'a');
  return "{\"admission_timeout_ms\":5000,\"attempt_id\":\"MODELED_ATTEMPT\","
         "\"helper_sha256\":" +
         quote(h) +
         ",\"native_duration_ms\":2000,\"operation_sha256\":" + quote(h) +
         ",\"permit_sha256\":" + quote(h) +
         ",\"phase_binding_sha256\":" + quote(h) +
         ",\"request_nonce\":" + quote(h) +
         ",\"runtime_registration_sha256\":" + quote(h) +
         ",\"sample_count\":2,\"schema\":\"rocell.native_usb_presence_request."
         "v1\"" +
         ",\"selected_identity_sha256\":" + quote(h) +
         ",\"session_id\":\"MODELED_SESSION\",\"source_sha256\":" + quote(h) +
         ",\"target_instance_id\":" + quote(target) +
         ",\"target_instance_id_sha256\":" + quote(sha256(target)) + "}";
}
Observation run(const std::string &scenario, std::uint32_t step = 1,
                bool cancelled = false) {
  const auto wire = input();
  FixtureApi api;
  api.target = "USB\\VID_1234&PID_5678\\UNIT_A";
  api.scenario = scenario;
  std::uint64_t ticks = 100;
  if (scenario == "late-size" || scenario == "stop-size" ||
      scenario == "late-list" || scenario == "stop-list") {
    const bool size_failure = scenario.find("size") != std::string::npos;
    api.scenario = size_failure ? "size-failed" : "list-failed";
    api.on_call = [&, size_failure] {
      if (api.calls == (size_failure ? 1U : 2U)) {
        if (scenario.find("late") == 0)
          ticks += 3000;
        else
          cancelled = true;
      }
    };
  }
  const auto result = observe(
      api, parse_request(wire, sha256(wire)), "INCAPABLE_FIXTURE",
      [&] { return cancelled; },
      [&] {
        ticks += step;
        return Moment{ticks, 1780000000000000000ULL + ticks * 1000000ULL};
      });
  expect(api.calls <= 4);
  expect(serialize(result).size() < output_limit);
  return result;
}
} // namespace
int main(int argc, char **argv) {
  try {
    if (argc == 3 && std::string(argv[1]) == "--wire") {
      std::cout << serialize(run(argv[2])) << '\n';
      return 0;
    }
    expect(argc == 1);
    for (const auto &scenario : {"absent", "same-model"})
      expect(run(scenario).outcome == "ABSENT");
    for (const auto &scenario : {"present", "mixed-case"})
      expect(run(scenario).outcome == "PRESENT");
    for (const auto &scenario :
         {"changed", "size-failed", "list-failed", "growth", "oversize",
          "zero-size", "unterminated", "wrong-filter", "duplicate", "many",
          "nonascii"}) {
      const auto result = run(scenario);
      expect(result.outcome == "HELD");
      expect(!result.error.empty());
    }
    expect(run("absent", 1, true).samples.empty());
    expect(run("absent", 1000).outcome == "HELD");
    const auto exception = run("exception");
    expect(exception.error == "API_EXCEPTION");
    expect(!exception.samples[0].native_code.has_value());
    expect(serialize(exception).find("MODELED_PRIVATE_DETAIL") ==
           std::string::npos);
    for (const auto &scenario :
         {"late-size", "stop-size", "late-list", "stop-list"}) {
      const auto result = run(scenario);
      expect(result.outcome == "HELD");
      expect(result.samples.size() == 1 && !result.samples[0].complete);
      expect(result.samples[0].native_code ==
             (std::string(scenario).find("size") != std::string::npos ? 13U
                                                                      : 26U));
    }
    const auto wire = input();
    for (const auto &bad : {"USB\\VID_1234&PID_5678&MI_00\\UNIT",
                            "USB\\VID_1234&PID_5678\\", "ROOT\\CAMERA\\X"}) {
      bool refused = false;
      try {
        const auto value = input(bad);
        (void)parse_request(value, sha256(value));
      } catch (...) {
        refused = true;
      }
      expect(refused);
    }
    bool refused = false;
    try {
      (void)parse_request(wire, std::string(64, 'b'));
    } catch (...) {
      refused = true;
    }
    expect(refused);
    std::cout << assertions << " incapable USB presence assertions passed\n";
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
