// Result formatting is separate so the pipe-only entry target need not link a
// metadata resolver/Windows adapter just to test REQUEST/READY/RELEASE/EOF.
#include <sstream>

#include "camera_activation_entry.h"

namespace rocell::activation_entry {
namespace {
const char* boolean(bool value) { return value ? "true" : "false"; }
std::string time_json(const std::optional<std::uint64_t>& value) {
  return value ? std::to_string(*value) : "null";
}
const char* comparison_name(activation_identity::Result result) {
  using R = activation_identity::Result;
  switch (result) {
    case R::Match:
      return "MATCH";
    case R::InvalidExpectation:
      return "INVALID_EXPECTATION";
    case R::EndpointChanged:
      return "ENDPOINT_CHANGED";
    case R::MappingUnavailable:
      return "MAPPING_UNAVAILABLE";
    case R::MappingChanged:
      return "MAPPING_CHANGED";
    case R::MetadataCleanupUnconfirmed:
      return "METADATA_CLEANUP_UNCONFIRMED";
    case R::DeviceUnavailable:
      return "DEVICE_UNAVAILABLE";
    case R::DriverUnavailable:
      return "DRIVER_UNAVAILABLE";
    case R::DetachedDeviceOrDriver:
      return "DETACHED_DEVICE_OR_DRIVER";
    case R::IncompleteObservation:
      return "INCOMPLETE_OBSERVATION";
    case R::InstanceChanged:
      return "INSTANCE_CHANGED";
    case R::ContainerChanged:
      return "CONTAINER_CHANGED";
    case R::LocationChanged:
      return "LOCATION_CHANGED";
    case R::DriverChanged:
      return "DRIVER_CHANGED";
  }
  throw std::runtime_error("ACTIVATION_COMPARISON_ENUM");
}
}  // namespace

std::string wrap_result(const Admitted& admitted, const activation_gate::Record& record,
                        const std::string& native) {
  if (!admitted.state.admitted()) throw std::runtime_error("ACTIVATION_ADMISSION_REQUIRED");
  const auto& state = admitted.state;
  std::ostringstream out;
  out << "{\"schema\":\"rocell.owned_native_camera_result.v2\",\"request_sha256\":\""
      << state.request().hash << "\",\"child_pid\":" << state.pid()
      << ",\"challenge_sha256\":\"" << state.challenge_hash() << "\",\"permit_sha256\":\""
      << state.request().permit()
      << "\",\"activation_identity\":{\"schema\":\"rocell.camera_pre_activation_identity.v1\""
      << ",\"expected_identity_sha256\":\"" << admitted.identity.payload_sha256
      << "\",\"original_identity_sha256\":\"" << admitted.identity.original_identity_sha256
      << "\",\"native_started_ms\":" << admitted.native_started_ms
      << ",\"native_deadline_ms\":" << admitted.native_deadline_ms
      << ",\"attempted\":" << boolean(record.attempted)
      << ",\"resolution_attempted\":" << boolean(record.resolution_attempted)
      << ",\"resolution_returned\":" << boolean(record.resolution_returned)
      << ",\"activation_callback_entered\":" << boolean(record.activation_callback_entered)
      << ",\"observation_started_ms\":" << time_json(record.observation_started_ms)
      << ",\"observation_returned_ms\":" << time_json(record.observation_returned_ms)
      << ",\"comparison\":";
  if (record.comparison)
    out << '"' << comparison_name(*record.comparison) << '"';
  else
    out << "null";
  out << ",\"metadata\":"
      << (record.metadata
              ? identity::serialize_identity_metadata(*record.metadata, record.limits)
              : "null")
      << "},\"native_receipt\":" << native << '}';
  return out.str();
}
}  // namespace rocell::activation_entry
