#pragma once
// Pure comparison for the future versioned acquisition entry. No operating-
// system API, camera activation, request parsing, clock or authority lives here.
#include <algorithm>
#include <string>
#include <vector>

#include "identity_metadata.h"

namespace rocell::activation_identity {
using identity::ContainerGuid;

// Supplied from independently retained/reviewed original metadata, never learned
// from the fresh observation being checked. Ephemeral devnode handles are absent.
struct Expected {
  std::wstring endpoint;
  std::wstring instance_id;
  ContainerGuid container;
  std::vector<std::wstring> location_paths;
  std::wstring driver_provider, driver_service, driver_version, driver_inf;
};

enum class Result {
  Match,
  InvalidExpectation,
  EndpointChanged,
  MappingUnavailable,
  MappingChanged,
  MetadataCleanupUnconfirmed,
  DeviceUnavailable,
  DriverUnavailable,
  DetachedDeviceOrDriver,
  IncompleteObservation,
  InstanceChanged,
  ContainerChanged,
  LocationChanged,
  DriverChanged,
};

inline bool text_valid(const std::wstring& value, std::size_t maximum) {
  static_assert(sizeof(wchar_t) == 2, "Windows UTF-16 comparison required");
  if (value.empty() || value.size() > maximum) return false;
  for (std::size_t i = 0; i < value.size(); ++i) {
    auto code = static_cast<std::uint16_t>(value[i]);
    if (code < 32 || code == 127) return false;
    if (code >= 0xd800 && code <= 0xdbff) {
      if (++i == value.size()) return false;
      code = static_cast<std::uint16_t>(value[i]);
      if (code < 0xdc00 || code > 0xdfff) return false;
    } else if (code >= 0xdc00 && code <= 0xdfff) {
      return false;
    }
  }
  return true;
}

inline bool same_guid(const ContainerGuid& left, const ContainerGuid& right) {
  return left.data1 == right.data1 && left.data2 == right.data2 && left.data3 == right.data3 &&
         left.data4 == right.data4;
}

inline bool expectation_valid(const Expected& expected) {
  if (!text_valid(expected.endpoint, 4096) || !text_valid(expected.instance_id, 1024) ||
      same_guid(expected.container, {}) || expected.location_paths.empty() ||
      expected.location_paths.size() > 16)
    return false;
  for (const auto* field : {&expected.driver_provider, &expected.driver_service,
                            &expected.driver_version, &expected.driver_inf}) {
    if (!text_valid(*field, 1024)) return false;
  }
  for (std::size_t i = 0; i < expected.location_paths.size(); ++i) {
    if (!text_valid(expected.location_paths[i], 1024) ||
        std::find(expected.location_paths.begin(), expected.location_paths.begin() + i,
                  expected.location_paths[i]) != expected.location_paths.begin() + i)
      return false;
  }
  return true;
}

template <class T>
inline bool observed(const identity::Observation<T>& field) {
  // A value paired with an error is not an observation, even if the caller
  // constructed the structure directly instead of using the metadata resolver.
  return field.observed() && field.unavailable.domain == identity::ErrorDomain::None &&
         field.unavailable.native_code == 0;
}

inline Result compare(const Expected& expected, const identity::IdentityMetadata& current) {
  if (!expectation_valid(expected)) return Result::InvalidExpectation;
  if (current.requested_endpoint != expected.endpoint) return Result::EndpointChanged;
  if (!observed(current.mapping.devnode) || !observed(current.mapping.interface_path))
    return Result::MappingUnavailable;
  if (*current.mapping.interface_path.value != expected.endpoint) return Result::MappingChanged;
  if (!current.mapping.cleanup_errors.empty()) return Result::MetadataCleanupUnconfirmed;
  if (!current.device) return Result::DeviceUnavailable;
  if (!current.driver) return Result::DriverUnavailable;
  const auto& device = *current.device;
  const auto& driver = *current.driver;
  if (device.devnode != *current.mapping.devnode.value || driver.devnode != device.devnode)
    return Result::DetachedDeviceOrDriver;
  if (current.physical_authority ||
      current.chain_end != identity::ChainEnd::ReachedObservedRoot ||
      !observed(current.observed_root) || current.api_calls == 0 || current.api_calls > 128 ||
      !observed(device.instance_id) || !observed(device.container_id) ||
      !observed(device.location_paths) || !observed(driver.provider) ||
      !observed(driver.service) || !observed(driver.version) || !observed(driver.inf_path))
    return Result::IncompleteObservation;
  // Validate the resolver's completion claim without treating parent handles as
  // persistent unit IDs. A truncated/cyclic chain cannot borrow a root label.
  if (current.parents.empty() || current.parents.size() > 16 ||
      current.parents.back().devnode != *current.observed_root.value)
    return Result::IncompleteObservation;
  for (std::size_t i = 0; i < current.parents.size(); ++i) {
    const auto node = current.parents[i].devnode;
    if (node == device.devnode ||
        std::any_of(current.parents.begin(), current.parents.begin() + i,
                    [node](const auto& parent) { return parent.devnode == node; }))
      return Result::IncompleteObservation;
  }
  if (*device.instance_id.value != expected.instance_id) return Result::InstanceChanged;
  if (!same_guid(*device.container_id.value, expected.container))
    return Result::ContainerChanged;
  // Exact observed path order, spelling and case: no normalization or fallback
  // to a friendly name, a camera index or a different parent device's driver.
  if (*device.location_paths.value != expected.location_paths) return Result::LocationChanged;
  if (*driver.provider.value != expected.driver_provider ||
      *driver.service.value != expected.driver_service ||
      *driver.version.value != expected.driver_version ||
      *driver.inf_path.value != expected.driver_inf)
    return Result::DriverChanged;
  return Result::Match;  // Metadata equality only; the caller still owns admission.
}
}  // namespace rocell::activation_identity
