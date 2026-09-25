#pragma once
// Metadata-only identity seam. All constructors are inert. No camera handle,
// COM/MF startup, registry writes, serial-number guessing or USB-speed inference.
#include <array>
#include <cstdint>
#include <functional>
#include <optional>
#include <string>
#include <utility>
#include <vector>

namespace rocell::identity {

using DevNode = std::uint32_t; // Ephemeral local Configuration Manager handle.
enum class ErrorDomain { None, Win32, ConfigurationManager, Contract };
enum class Unavailable {
  None, NotRequested, ApiFailure, WrongPropertyType, MalformedValue,
  ByteLimit, Cancelled, Deadline, ClockChanged, CallLimit,
};
struct Error {
  Unavailable reason = Unavailable::NotRequested;
  ErrorDomain domain = ErrorDomain::None;
  std::uint32_t native_code = 0;
};
template <class T> struct Observation {
  std::optional<T> value;
  Error unavailable;
  bool observed() const { return value.has_value() && unavailable.reason == Unavailable::None; }
  static Observation observed_value(T data) {
    return {std::move(data), {Unavailable::None, ErrorDomain::None, 0}};
  }
  static Observation missing(Error reason) { return {std::nullopt, reason}; }
};
struct ContainerGuid {
  std::uint32_t data1 = 0;
  std::uint16_t data2 = 0, data3 = 0;
  std::array<std::uint8_t, 8> data4{};
};
enum class Property { ContainerId, LocationPaths, DriverProvider, DriverService, DriverVersion, DriverInfPath };
// Values are DEVPROP_TYPE_GUID, DEVPROP_TYPE_STRING_LIST and DEVPROP_TYPE_STRING. The Windows
// translation unit statically checks these public wire-type constants.
constexpr std::uint32_t kGuidPropertyType = 0x0000000d;
constexpr std::uint32_t kStringListPropertyType = 0x00002012;
constexpr std::uint32_t kStringPropertyType = 0x00000012;
struct RawProperty {
  std::uint32_t property_type = 0;
  std::vector<std::uint8_t> bytes;
};
struct EndpointMapping {
  Observation<DevNode> devnode;
  Observation<std::wstring> interface_path;
  // Metadata information-set cleanup is not camera deactivation. Errors are
  // retained even when some identity fields were successfully observed.
  std::vector<Error> cleanup_errors;
};

class IdentityMetadataApi {
public:
  virtual ~IdentityMetadataApi() = default;
  virtual EndpointMapping map_endpoint(const std::wstring& opaque_endpoint) = 0;
  virtual Observation<std::wstring> instance_id(DevNode node, std::uint32_t max_chars) = 0;
  virtual Observation<RawProperty> property(DevNode node, Property key, std::uint32_t max_bytes) = 0;
  virtual Observation<DevNode> root_node() = 0;
  virtual Observation<DevNode> parent_node(DevNode node) = 0;
};

class WindowsIdentityMetadataApi final : public IdentityMetadataApi {
public:
  // The default constructor has no owned handle or operating-system calls.
  EndpointMapping map_endpoint(const std::wstring& opaque_endpoint) override;
  Observation<std::wstring> instance_id(DevNode node, std::uint32_t max_chars) override;
  Observation<RawProperty> property(DevNode node, Property key, std::uint32_t max_bytes) override;
  Observation<DevNode> root_node() override;
  Observation<DevNode> parent_node(DevNode node) override;
};

struct Limits {
  std::uint32_t max_parent_nodes = 8;
  std::uint32_t max_property_bytes = 16 * 1024;
  std::uint32_t max_total_property_bytes = 128 * 1024;
  std::uint32_t max_instance_chars = 1024;
  std::uint32_t max_location_paths = 16;
  std::uint32_t duration_ms = 5000;
};
struct RunControl {
  std::function<std::uint64_t()> monotonic_ms;
  std::function<bool()> cancelled;
};
struct NodeMetadata {
  DevNode devnode = 0;
  Observation<std::wstring> instance_id;
  Observation<ContainerGuid> container_id;
  Observation<std::vector<std::wstring>> location_paths;
};
struct DriverMetadata {
  DevNode devnode = 0;
  Observation<std::wstring> provider, service, version, inf_path;
};
enum class ChainEnd {
  NotRequested, ReachedObservedRoot, ParentUnavailable, ParentCycle,
  DepthLimit, Cancelled, Deadline, ClockChanged, CallLimit,
};
struct IdentityMetadata {
  std::wstring requested_endpoint;
  EndpointMapping mapping;
  std::optional<NodeMetadata> device;
  // Only the exact mapped endpoint node; never filled from an ancestor.
  std::optional<DriverMetadata> driver;
  std::vector<NodeMetadata> parents; // Immediate parent first, observed root last.
  Observation<DevNode> observed_root;
  ChainEnd chain_end = ChainEnd::NotRequested;
  Error chain_error;
  std::uint32_t api_calls = 0;
  std::uint32_t observed_property_bytes = 0;
  bool physical_authority = false; // Never promoted by this diagnostic seam.
};

Observation<ContainerGuid> decode_container_guid(const RawProperty& raw);
Observation<std::wstring> decode_driver_string(const RawProperty& raw, std::uint32_t max_chars);
Observation<std::vector<std::wstring>> decode_location_paths(
    const RawProperty& raw, std::uint32_t max_paths, std::uint32_t max_chars);

// Requires an explicitly supplied API, clock and cancellation hook. Tests use
// an incapable fake. Caller must also supply an out-of-process wall deadline:
// a Windows API stuck inside one call cannot be interrupted by this resolver.
IdentityMetadata resolve_identity_metadata(IdentityMetadataApi& api,
    const std::wstring& opaque_endpoint, const Limits& limits, const RunControl& control);

// Separate versioned metadata receipt. This never extends/loosens the existing
// rocell.windows_camera.v1 capture receipt and includes no frame payloads.
std::string serialize_identity_metadata(const IdentityMetadata& metadata, const Limits& limits);

} // namespace rocell::identity
