// No Windows libraries/adapter, process launcher, device or file implementation.
#include <functional>
#include <iostream>
#include <stdexcept>

#include "camera_activation_identity.h"

namespace ai = rocell::activation_identity;
namespace id = rocell::identity;
namespace {
unsigned checks = 0;
void check(bool condition) {
  ++checks;
  if (!condition) throw std::runtime_error("ACTIVATION_IDENTITY_TEST_FAILED");
}
template <class T>
auto seen(T value) {
  return id::Observation<T>::observed_value(std::move(value));
}
ai::Expected expected() {
  return {L"opaque-camera-endpoint",
          L"USB\\UNIT_1",
          {1, 2, 3, {4, 5, 6, 7, 8, 9, 10, 11}},
          {L"PCIROOT(0)#USBROOT(0)#USB(1)", L"ACPI(1)#USB(1)"},
          L"Microsoft",
          L"usbvideo",
          L"10.0.1.2",
          L"usbvideo.inf"};
}
id::IdentityMetadata current(const ai::Expected& pin) {
  id::IdentityMetadata value;
  value.requested_endpoint = pin.endpoint;
  value.mapping.devnode = seen<id::DevNode>(7);
  value.mapping.interface_path = seen(pin.endpoint);
  value.device =
      id::NodeMetadata{7, seen(pin.instance_id), seen(pin.container), seen(pin.location_paths)};
  value.driver = id::DriverMetadata{7, seen(pin.driver_provider), seen(pin.driver_service),
                                    seen(pin.driver_version), seen(pin.driver_inf)};
  value.observed_root = seen<id::DevNode>(1);
  value.parents = {{8, seen<std::wstring>(L"USB\\PARENT"), {}, {}},
                   {1, seen<std::wstring>(L"HTREE\\ROOT\\0"), {}, {}}};
  value.chain_end = id::ChainEnd::ReachedObservedRoot;
  value.api_calls = 17;
  return value;
}
void changed(const std::function<void(id::IdentityMetadata&)>& mutate, ai::Result result) {
  auto pin = expected();
  auto value = current(pin);
  mutate(value);
  check(ai::compare(pin, value) == result);
}
}  // namespace

int main() {
  try {
    const auto pin = expected();
    check(ai::expectation_valid(pin));
    check(ai::compare(pin, current(pin)) == ai::Result::Match);
    // Handles can legitimately change between observations. Only consistency
    // within this new observation is required; handles are not persistent IDs.
    changed(
        [](auto& v) {
          v.mapping.devnode = seen<id::DevNode>(99);
          v.device->devnode = 99;
          v.driver->devnode = 99;
        },
        ai::Result::Match);
    changed([](auto& v) { v.requested_endpoint += L"other"; }, ai::Result::EndpointChanged);
    changed([](auto& v) { v.mapping.devnode = {}; }, ai::Result::MappingUnavailable);
    changed([](auto& v) { v.mapping.interface_path = {}; }, ai::Result::MappingUnavailable);
    changed([](auto& v) { v.mapping.interface_path.value = L"other"; },
            ai::Result::MappingChanged);
    changed(
        [](auto& v) {
          v.mapping.cleanup_errors.push_back(
              {id::Unavailable::ApiFailure, id::ErrorDomain::Win32, 5});
        },
        ai::Result::MetadataCleanupUnconfirmed);
    changed([](auto& v) { v.device.reset(); }, ai::Result::DeviceUnavailable);
    changed([](auto& v) { v.driver.reset(); }, ai::Result::DriverUnavailable);
    changed([](auto& v) { v.parents.clear(); }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.parents.back().devnode = 10; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.parents.front().devnode = 1; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.parents.front().devnode = 7; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.parents.resize(17); }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.device->devnode = 9; }, ai::Result::DetachedDeviceOrDriver);
    changed([](auto& v) { v.driver->devnode = 9; }, ai::Result::DetachedDeviceOrDriver);
    changed([](auto& v) { v.device->instance_id.value = L"USB\\REPLACEMENT"; },
            ai::Result::InstanceChanged);
    changed([](auto& v) { ++v.device->container_id.value->data1; },
            ai::Result::ContainerChanged);
    changed([](auto& v) { v.device->location_paths.value->pop_back(); },
            ai::Result::LocationChanged);
    changed(
        [](auto& v) {
          std::reverse(v.device->location_paths.value->begin(),
                       v.device->location_paths.value->end());
        },
        ai::Result::LocationChanged);
    for (const auto member : {&id::DriverMetadata::provider, &id::DriverMetadata::service,
                              &id::DriverMetadata::version, &id::DriverMetadata::inf_path}) {
      changed([member](auto& v) { (v.driver.value().*member).value = L"other"; },
              ai::Result::DriverChanged);
      changed([member](auto& v) { v.driver.value().*member = {}; },
              ai::Result::IncompleteObservation);
      changed([member](auto& v) { (v.driver.value().*member).unavailable.native_code = 5; },
              ai::Result::IncompleteObservation);
    }
    changed([](auto& v) { v.device->instance_id = {}; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.device->container_id = {}; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.device->location_paths = {}; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.observed_root = {}; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.physical_authority = true; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.api_calls = 0; }, ai::Result::IncompleteObservation);
    changed([](auto& v) { v.api_calls = 129; }, ai::Result::IncompleteObservation);
    for (const auto end :
         {id::ChainEnd::NotRequested, id::ChainEnd::ParentUnavailable,
          id::ChainEnd::ParentCycle, id::ChainEnd::DepthLimit, id::ChainEnd::Cancelled,
          id::ChainEnd::Deadline, id::ChainEnd::ClockChanged, id::ChainEnd::CallLimit}) {
      changed([end](auto& v) { v.chain_end = end; }, ai::Result::IncompleteObservation);
    }
    for (const auto member : {&ai::Expected::endpoint, &ai::Expected::instance_id,
                              &ai::Expected::driver_provider, &ai::Expected::driver_service,
                              &ai::Expected::driver_version, &ai::Expected::driver_inf}) {
      for (const auto& bad :
           {std::wstring{}, std::wstring(L"bad\n"), std::wstring(4097, L'x'),
            std::wstring(1, wchar_t(0xd800)), std::wstring(1, wchar_t(0xdc00))}) {
        auto invalid = pin;
        invalid.*member = bad;
        check(ai::compare(invalid, current(invalid)) == ai::Result::InvalidExpectation);
      }
    }
    for (const auto& bad : {std::vector<std::wstring>{}, std::vector<std::wstring>(17, L"path"),
                            std::vector<std::wstring>{L"same", L"same"},
                            std::vector<std::wstring>{std::wstring(1025, L'x')}}) {
      auto invalid = pin;
      invalid.location_paths = bad;
      check(ai::compare(invalid, current(invalid)) == ai::Result::InvalidExpectation);
    }
    auto invalid = pin;
    invalid.container = {};
    check(ai::compare(invalid, current(invalid)) == ai::Result::InvalidExpectation);
    std::cout
        << checks
        << " incapable activation-identity comparison assertions passed; device calls=0\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << "; assertion=" << checks << '\n';
    return 1;
  }
}
