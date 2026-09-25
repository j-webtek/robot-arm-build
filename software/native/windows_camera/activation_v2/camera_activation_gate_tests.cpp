// In-memory callbacks only. No resolver, OS, device or process implementation.
#include <iostream>
#include <string>

#include "camera_activation_gate.h"

namespace ai = rocell::activation_identity;
namespace ag = rocell::activation_gate;
namespace id = rocell::identity;
namespace {
unsigned assertions = 0;
void check(bool ok) {
  ++assertions;
  if (!ok) throw std::runtime_error("ACTIVATION_GATE_TEST_FAILED");
}
template <class T>
auto seen(T value) {
  return id::Observation<T>::observed_value(std::move(value));
}
ai::Expected expected() {
  return {L"MODELED-endpoint",
          L"USB\\MODELED_UNIT",
          {1, 2, 3, {1, 2, 3, 4, 5, 6, 7, 8}},
          {L"PCIROOT(0)#USB(1)"},
          L"MODELED provider",
          L"usbvideo",
          L"1.2.3.4",
          L"usbvideo.inf"};
}
id::IdentityMetadata observation(const ai::Expected& e) {
  id::IdentityMetadata result;
  result.requested_endpoint = e.endpoint;
  result.mapping.devnode = seen<id::DevNode>(7);
  result.mapping.interface_path = seen(e.endpoint);
  result.device =
      id::NodeMetadata{7, seen(e.instance_id), seen(e.container), seen(e.location_paths)};
  result.driver = id::DriverMetadata{7, seen(e.driver_provider), seen(e.driver_service),
                                     seen(e.driver_version), seen(e.driver_inf)};
  result.observed_root = seen<id::DevNode>(1);
  result.parents = {{1, seen<std::wstring>(L"HTREE\\MODELED_ROOT"), {}, {}}};
  result.chain_end = id::ChainEnd::ReachedObservedRoot;
  result.api_calls = 13;
  return result;
}
struct Case {
  ag::Gate gate;
  ai::Expected pin = expected();
  std::uint64_t now = 1500;
  bool cancelled = false;
  unsigned resolves = 0, activation_callbacks = 0;
  std::function<void(id::IdentityMetadata&)> fault = [](auto&) {};
  void run() {
    gate.run(
        pin, 1000, 6000, {[&]() { return now; }, [&]() { return cancelled; }},
        [&](const id::Limits& limits, const id::RunControl&) {
          ++resolves;
          check(gate.record().resolution_attempted && !gate.record().resolution_returned);
          check(limits.duration_ms == 4500 && limits.max_parent_nodes == 16);
          auto result = observation(pin);
          fault(result);
          return result;
        },
        [&]() {
          check(gate.record().resolution_returned && gate.record().activation_callback_entered);
          check(gate.record().comparison == ai::Result::Match);
          ++activation_callbacks;
        });
  }
};
template <class F>
void fails(F action, const std::string& expected_code) {
  try {
    action();
    check(false);
  } catch (const ag::Error& e) {
    check(e.what() == expected_code);
  }
}
}  // namespace

int main() {
  try {
    Case success;
    success.run();
    check(success.resolves == 1 && success.activation_callbacks == 1);
    check(success.gate.record().metadata->api_calls == 13);
    check(success.gate.record().observation_started_ms == 1500);
    check(success.gate.record().observation_returned_ms == 1500);
    fails([&]() { success.run(); }, "ACTIVATION_GUARD_ALREADY_ATTEMPTED");
    check(success.resolves == 1 && success.activation_callbacks == 1);

    for (const auto& mutate : std::vector<std::function<void(id::IdentityMetadata&)>>{
             [](auto& m) { m.device->instance_id.value = L"USB\\REPLACED_UNIT"; },
             [](auto& m) { ++m.device->container_id.value->data1; },
             [](auto& m) { m.device->location_paths.value->push_back(L"new port"); },
             [](auto& m) { m.driver->version.value = L"updated-driver"; },
             [](auto& m) { m.driver.reset(); },
             [](auto& m) { m.mapping.cleanup_errors.push_back({}); },
             [](auto& m) { m.chain_end = id::ChainEnd::DepthLimit; }}) {
      Case changed;
      changed.fault = mutate;
      fails([&]() { changed.run(); }, "ACTIVATION_IDENTITY_COMPARISON_FAILED");
      check(changed.resolves == 1 && changed.activation_callbacks == 0);
      check(changed.gate.record().metadata.has_value());
      check(changed.gate.record().resolution_returned);
      check(!changed.gate.record().activation_callback_entered);
      fails([&]() { changed.run(); }, "ACTIVATION_GUARD_ALREADY_ATTEMPTED");
    }
    for (const auto& kind : {"cancel", "deadline", "rollback"}) {
      Case early;
      if (std::string(kind) == "cancel") early.cancelled = true;
      if (std::string(kind) == "deadline") early.now = 6000;
      if (std::string(kind) == "rollback") early.now = 999;
      const auto code = std::string("ACTIVATION_GUARD_") +
                        (std::string(kind) == "cancel"     ? "CANCELLED"
                         : std::string(kind) == "deadline" ? "DEADLINE"
                                                           : "CLOCK_CHANGED");
      fails([&]() { early.run(); }, code);
      check(early.resolves == 0 && early.activation_callbacks == 0);
      check(!early.gate.record().metadata && !early.gate.record().resolution_attempted);

      Case late;
      late.fault = [&](auto&) {
        if (std::string(kind) == "cancel") late.cancelled = true;
        if (std::string(kind) == "deadline") late.now = 6000;
        if (std::string(kind) == "rollback") late.now = 1499;
      };
      fails([&]() { late.run(); }, code);
      check(late.resolves == 1 && late.activation_callbacks == 0);
      check(late.gate.record().metadata && late.gate.record().resolution_returned);
      check(!late.gate.record().comparison);
    }
    Case lost;
    lost.fault = [](auto&) { throw std::runtime_error("MODELED resolver threw after a call"); };
    try {
      lost.run();
      check(false);
    } catch (const std::runtime_error& e) {
      check(std::string(e.what()) == "MODELED resolver threw after a call");
    }
    check(lost.resolves == 1 && lost.activation_callbacks == 0);
    check(lost.gate.record().resolution_attempted && !lost.gate.record().resolution_returned);
    check(!lost.gate.record().metadata);  // Unavailable, not an invented zero-call receipt.

    ag::Gate invalid;
    unsigned callbacks = 0;
    fails([&]() { invalid.run(expected(), 1000, 6001, {}, {}, [&]() { ++callbacks; }); },
          "ACTIVATION_GUARD_CONTEXT_INVALID");
    check(callbacks == 0 && !invalid.record().resolution_attempted);
    Case insufficient;
    insufficient.now = 5901;
    fails([&]() { insufficient.run(); }, "ACTIVATION_IDENTITY_BUDGET_INSUFFICIENT");
    check(insufficient.resolves == 0 && insufficient.activation_callbacks == 0);
    check(!insufficient.gate.record().observation_started_ms);
    ag::Gate minimum;
    minimum.run(
        expected(), 1000, 6000, {[]() { return 5900; }, []() { return false; }},
        [&](const auto& limits, const auto&) {
          check(limits.duration_ms == 100);
          return observation(expected());
        },
        [&]() { ++callbacks; });
    check(callbacks == 1 && minimum.record().activation_callback_entered);
    std::cout << "PASS: " << assertions << " incapable activation-order assertions\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
