#include "identity_metadata.h"
#include <windows.h>
#include <setupapi.h>
#include <cfgmgr32.h>
#include <initguid.h>
#include <devpkey.h>
#include <algorithm>
#include <cstring>
#include <iomanip>
#include <set>
#include <sstream>
#include <stdexcept>

namespace rocell::identity {
static_assert(sizeof(wchar_t) == 2, "The Windows provider returns UTF-16 code units");
static_assert(kGuidPropertyType == DEVPROP_TYPE_GUID);
static_assert(kStringListPropertyType == DEVPROP_TYPE_STRING_LIST);
static_assert(kStringPropertyType == DEVPROP_TYPE_STRING);
namespace {
Error invalid(Unavailable why) { return {why, ErrorDomain::Contract, 0}; }
Error win32(DWORD code) { return {Unavailable::ApiFailure, ErrorDomain::Win32, code}; }
Error cm(CONFIGRET code) { return {Unavailable::ApiFailure, ErrorDomain::ConfigurationManager, code}; }
bool valid_text(const std::wstring& value, std::size_t maximum) {
  if (value.empty() || value.size() > maximum) return false;
  for (std::size_t i = 0; i < value.size(); ++i) {
    const auto code = static_cast<std::uint16_t>(value[i]);
    if (code < 32 || code == 127) return false;
    if (code >= 0xd800 && code <= 0xdbff) {
      if (++i >= value.size()) return false;
      const auto low = static_cast<std::uint16_t>(value[i]);
      if (low < 0xdc00 || low > 0xdfff) return false;
    } else if (code >= 0xdc00 && code <= 0xdfff) return false;
  }
  return true;
}
std::uint16_t u16(const std::vector<std::uint8_t>& bytes, std::size_t at) {
  return static_cast<std::uint16_t>(bytes.at(at) | (std::uint16_t(bytes.at(at + 1)) << 8));
}
std::uint32_t u32(const std::vector<std::uint8_t>& bytes, std::size_t at) {
  return std::uint32_t(u16(bytes, at)) | (std::uint32_t(u16(bytes, at + 2)) << 16);
}
struct MetadataSet {
  HDEVINFO handle = INVALID_HANDLE_VALUE;
  SP_DEVICE_INTERFACE_DATA interface_data{};
  bool interface_added = false;
  MetadataSet() { interface_data.cbSize = sizeof(interface_data); }
  ~MetadataSet() {
    // Exception safety only. Normal completion uses close() and retains errors.
    if (handle != INVALID_HANDLE_VALUE) {
      if (interface_added) SetupDiDeleteDeviceInterfaceData(handle, &interface_data);
      SetupDiDestroyDeviceInfoList(handle);
    }
  }
  std::vector<Error> close() {
    std::vector<Error> errors;
    if (handle == INVALID_HANDLE_VALUE) return errors;
    if (interface_added && !SetupDiDeleteDeviceInterfaceData(handle, &interface_data)) errors.push_back(win32(GetLastError()));
    interface_added = false;
    if (!SetupDiDestroyDeviceInfoList(handle)) errors.push_back(win32(GetLastError()));
    handle = INVALID_HANDLE_VALUE;
    return errors;
  }
};
} // namespace

EndpointMapping WindowsIdentityMetadataApi::map_endpoint(const std::wstring& endpoint) {
  EndpointMapping result;
  if (!valid_text(endpoint, 4096)) {
    result.devnode = Observation<DevNode>::missing(invalid(Unavailable::MalformedValue));
    return result;
  }
  MetadataSet owner;
  owner.handle = SetupDiCreateDeviceInfoList(nullptr, nullptr);
  if (owner.handle == INVALID_HANDLE_VALUE) {
    result.devnode = Observation<DevNode>::missing(win32(GetLastError()));
    return result;
  }
  // Opens an interface entry in an in-memory information set, not a camera
  // capture handle. Do not call CreateFile/ActivateObject on the device path.
  if (!SetupDiOpenDeviceInterfaceW(owner.handle, endpoint.c_str(), 0, &owner.interface_data)) {
    result.devnode = Observation<DevNode>::missing(win32(GetLastError()));
  } else {
    owner.interface_added = true;
    DWORD required = 0;
    SP_DEVINFO_DATA data{}; data.cbSize = sizeof(data);
    const BOOL sized = SetupDiGetDeviceInterfaceDetailW(owner.handle, &owner.interface_data,
        nullptr, 0, &required, &data);
    const DWORD size_error = sized ? ERROR_SUCCESS : GetLastError();
    if (sized || size_error != ERROR_INSUFFICIENT_BUFFER) {
      result.devnode = Observation<DevNode>::missing(sized ? invalid(Unavailable::MalformedValue) : win32(size_error));
    } else if (required < sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W) || required > 16 * 1024) {
      result.devnode = Observation<DevNode>::missing(invalid(Unavailable::ByteLimit));
    } else {
      std::vector<std::uint8_t> buffer(required);
      auto* detail = reinterpret_cast<SP_DEVICE_INTERFACE_DETAIL_DATA_W*>(buffer.data());
      detail->cbSize = sizeof(SP_DEVICE_INTERFACE_DETAIL_DATA_W);
      DWORD actual = 0;
      if (!SetupDiGetDeviceInterfaceDetailW(owner.handle, &owner.interface_data, detail,
          required, &actual, &data)) {
        // No retry if a device disappears or the size changes between calls.
        result.devnode = Observation<DevNode>::missing(win32(GetLastError()));
      } else if (actual > required || actual < offsetof(SP_DEVICE_INTERFACE_DETAIL_DATA_W, DevicePath) + sizeof(wchar_t)) {
        result.devnode = Observation<DevNode>::missing(invalid(Unavailable::MalformedValue));
      } else {
        const std::size_t capacity = (actual - offsetof(SP_DEVICE_INTERFACE_DETAIL_DATA_W, DevicePath)) / sizeof(wchar_t);
        const auto end = std::find(detail->DevicePath, detail->DevicePath + capacity, L'\0');
        const std::wstring path(detail->DevicePath, end);
        if (end == detail->DevicePath + capacity || !valid_text(path, 4096)) {
          result.devnode = Observation<DevNode>::missing(invalid(Unavailable::MalformedValue));
        } else {
          result.devnode = Observation<DevNode>::observed_value(data.DevInst);
          result.interface_path = Observation<std::wstring>::observed_value(path);
        }
      }
    }
  }
  result.cleanup_errors = owner.close();
  return result;
}

Observation<std::wstring> WindowsIdentityMetadataApi::instance_id(DevNode node, std::uint32_t max_chars) {
  if (max_chars == 0 || max_chars > 4096) return Observation<std::wstring>::missing(invalid(Unavailable::ByteLimit));
  ULONG length = 0;
  CONFIGRET status = CM_Get_Device_ID_Size(&length, node, 0);
  if (status != CR_SUCCESS) return Observation<std::wstring>::missing(cm(status));
  // CM length excludes the terminating NULL. Never infer an identifier from
  // an endpoint substring when the actual property cannot be read.
  if (length == 0 || length > max_chars) return Observation<std::wstring>::missing(invalid(Unavailable::ByteLimit));
  std::vector<wchar_t> buffer(static_cast<std::size_t>(length) + 1, L'\xffff');
  status = CM_Get_Device_IDW(node, buffer.data(), length + 1, 0);
  if (status != CR_SUCCESS) return Observation<std::wstring>::missing(cm(status));
  if (buffer[length] != L'\0') return Observation<std::wstring>::missing(invalid(Unavailable::MalformedValue));
  std::wstring value(buffer.data(), length);
  if (!valid_text(value, max_chars)) return Observation<std::wstring>::missing(invalid(Unavailable::MalformedValue));
  return Observation<std::wstring>::observed_value(std::move(value));
}

Observation<RawProperty> WindowsIdentityMetadataApi::property(DevNode node, Property key, std::uint32_t max_bytes) {
  if (max_bytes == 0 || max_bytes > 64 * 1024) return Observation<RawProperty>::missing(invalid(Unavailable::ByteLimit));
  const DEVPROPKEY* property_key = nullptr;
  if (key == Property::ContainerId) property_key = &DEVPKEY_Device_ContainerId;
  else if (key == Property::LocationPaths) property_key = &DEVPKEY_Device_LocationPaths;
  else if (key == Property::DriverProvider) property_key = &DEVPKEY_Device_DriverProvider;
  else if (key == Property::DriverService) property_key = &DEVPKEY_Device_Service;
  else if (key == Property::DriverVersion) property_key = &DEVPKEY_Device_DriverVersion;
  else if (key == Property::DriverInfPath) property_key = &DEVPKEY_Device_DriverInfPath;
  else return Observation<RawProperty>::missing(invalid(Unavailable::WrongPropertyType));
  DEVPROPTYPE type = 0;
  ULONG length = 0;
  CONFIGRET status = CM_Get_DevNode_PropertyW(node, property_key, &type, nullptr, &length, 0);
  if (status != CR_BUFFER_SMALL) return Observation<RawProperty>::missing(status == CR_SUCCESS ? invalid(Unavailable::MalformedValue) : cm(status));
  if (length == 0 || length > max_bytes) return Observation<RawProperty>::missing(invalid(Unavailable::ByteLimit));
  RawProperty result; result.bytes.resize(length);
  ULONG actual = length;
  status = CM_Get_DevNode_PropertyW(node, property_key, &type, result.bytes.data(), &actual, 0);
  if (status != CR_SUCCESS) return Observation<RawProperty>::missing(cm(status));
  if (actual > length) return Observation<RawProperty>::missing(invalid(Unavailable::ByteLimit));
  result.bytes.resize(actual); result.property_type = type;
  return Observation<RawProperty>::observed_value(std::move(result));
}

Observation<DevNode> WindowsIdentityMetadataApi::root_node() {
  DEVINST root = 0;
  const CONFIGRET status = CM_Locate_DevNodeW(&root, nullptr, CM_LOCATE_DEVNODE_NORMAL);
  return status == CR_SUCCESS ? Observation<DevNode>::observed_value(root) : Observation<DevNode>::missing(cm(status));
}
Observation<DevNode> WindowsIdentityMetadataApi::parent_node(DevNode node) {
  DEVINST parent = 0;
  const CONFIGRET status = CM_Get_Parent(&parent, node, 0);
  return status == CR_SUCCESS ? Observation<DevNode>::observed_value(parent) : Observation<DevNode>::missing(cm(status));
}

Observation<std::wstring> decode_driver_string(const RawProperty& raw, std::uint32_t max_chars) {
  using Result = Observation<std::wstring>;
  if (raw.property_type != kStringPropertyType) return Result::missing(invalid(Unavailable::WrongPropertyType));
  if (raw.bytes.size() < 4 || raw.bytes.size() % 2 || raw.bytes.size() > 64 * 1024 ||
      u16(raw.bytes, raw.bytes.size() - 2) != 0) return Result::missing(invalid(Unavailable::MalformedValue));
  if (raw.bytes.size() / 2 - 1 > max_chars) return Result::missing(invalid(Unavailable::ByteLimit));
  std::wstring value;
  for (std::size_t at = 0; at + 2 < raw.bytes.size(); at += 2) value.push_back(static_cast<wchar_t>(u16(raw.bytes, at)));
  if (!valid_text(value, max_chars)) return Result::missing(invalid(Unavailable::MalformedValue));
  return Result::observed_value(std::move(value));
}

Observation<ContainerGuid> decode_container_guid(const RawProperty& raw) {
  if (raw.property_type != kGuidPropertyType) return Observation<ContainerGuid>::missing(invalid(Unavailable::WrongPropertyType));
  if (raw.bytes.size() != 16) return Observation<ContainerGuid>::missing(invalid(Unavailable::MalformedValue));
  ContainerGuid value;
  value.data1 = u32(raw.bytes, 0); value.data2 = u16(raw.bytes, 4); value.data3 = u16(raw.bytes, 6);
  std::copy(raw.bytes.begin() + 8, raw.bytes.end(), value.data4.begin());
  return Observation<ContainerGuid>::observed_value(value);
}
Observation<std::vector<std::wstring>> decode_location_paths(
    const RawProperty& raw, std::uint32_t max_paths, std::uint32_t max_chars) {
  using Result = Observation<std::vector<std::wstring>>;
  if (raw.property_type != kStringListPropertyType) return Result::missing(invalid(Unavailable::WrongPropertyType));
  if (raw.bytes.size() < 4 || raw.bytes.size() % 2 || raw.bytes.size() > 64 * 1024 ||
      u16(raw.bytes, raw.bytes.size() - 2) || u16(raw.bytes, raw.bytes.size() - 4)) {
    return Result::missing(invalid(Unavailable::MalformedValue));
  }
  std::vector<std::wstring> values;
  std::wstring value;
  for (std::size_t at = 0; at + 2 < raw.bytes.size(); at += 2) {
    const auto code = u16(raw.bytes, at);
    if (code != 0) {
      value.push_back(static_cast<wchar_t>(code));
      if (value.size() > max_chars) return Result::missing(invalid(Unavailable::ByteLimit));
      continue;
    }
    if (value.empty()) {
      // An empty list is exactly two NULL UTF-16 characters. An interior empty
      // path or extra terminators would make parsing ambiguous.
      if (values.empty() && raw.bytes.size() == 4) return Result::observed_value({});
      return Result::missing(invalid(Unavailable::MalformedValue));
    }
    if (!valid_text(value, max_chars)) return Result::missing(invalid(Unavailable::MalformedValue));
    values.push_back(std::move(value)); value.clear();
    if (values.size() > max_paths) return Result::missing(invalid(Unavailable::ByteLimit));
  }
  if (!value.empty()) return Result::missing(invalid(Unavailable::MalformedValue));
  return Result::observed_value(std::move(values));
}

IdentityMetadata resolve_identity_metadata(IdentityMetadataApi& api,
    const std::wstring& endpoint, const Limits& limits, const RunControl& control) {
  if (!valid_text(endpoint, 4096) || !control.monotonic_ms || !control.cancelled ||
      limits.max_parent_nodes > 16 || limits.max_property_bytes == 0 || limits.max_property_bytes > 64 * 1024 ||
      limits.max_total_property_bytes < limits.max_property_bytes || limits.max_total_property_bytes > 512 * 1024 ||
      limits.max_instance_chars == 0 || limits.max_instance_chars > 4096 ||
      limits.max_location_paths == 0 || limits.max_location_paths > 32 ||
      limits.duration_ms == 0 || limits.duration_ms > 30000) {
    throw std::invalid_argument("Invalid identity metadata request or budget");
  }
  IdentityMetadata result; result.requested_endpoint = endpoint;
  const std::uint64_t started = control.monotonic_ms();
  struct Stopped { Unavailable reason; };
  auto before_call = [&]() {
    if (control.cancelled()) throw Stopped{Unavailable::Cancelled};
    const auto now = control.monotonic_ms();
    if (now < started) throw Stopped{Unavailable::ClockChanged};
    if (now - started >= limits.duration_ms) throw Stopped{Unavailable::Deadline};
    if (result.api_calls >= 128) throw Stopped{Unavailable::CallLimit};
    ++result.api_calls;
  };
  auto read_property = [&](DevNode node, Property property) -> Observation<RawProperty> {
    const auto remaining = limits.max_total_property_bytes - result.observed_property_bytes;
    if (remaining == 0) return Observation<RawProperty>::missing(invalid(Unavailable::ByteLimit));
    const auto maximum = std::min(limits.max_property_bytes, remaining);
    before_call();
    auto raw = api.property(node, property, maximum);
    if (raw.observed()) {
      if (raw.value->bytes.size() > limits.max_property_bytes ||
          raw.value->bytes.size() > limits.max_total_property_bytes - result.observed_property_bytes) {
        return Observation<RawProperty>::missing(invalid(Unavailable::ByteLimit));
      }
      result.observed_property_bytes += static_cast<std::uint32_t>(raw.value->bytes.size());
    }
    return raw;
  };
  auto read_node = [&](DevNode node) {
    NodeMetadata data; data.devnode = node;
    before_call(); data.instance_id = api.instance_id(node, limits.max_instance_chars);
    if (data.instance_id.observed() && !valid_text(*data.instance_id.value, limits.max_instance_chars))
      data.instance_id = Observation<std::wstring>::missing(invalid(Unavailable::MalformedValue));
    const auto container = read_property(node, Property::ContainerId);
    data.container_id = container.observed() ? decode_container_guid(*container.value) : Observation<ContainerGuid>::missing(container.unavailable);
    const auto locations = read_property(node, Property::LocationPaths);
    data.location_paths = locations.observed() ? decode_location_paths(*locations.value, limits.max_location_paths, limits.max_instance_chars) : Observation<std::vector<std::wstring>>::missing(locations.unavailable);
    return data;
  };
  try {
    before_call(); result.mapping = api.map_endpoint(endpoint);
    if (!result.mapping.devnode.observed()) return result;
    const DevNode selected = *result.mapping.devnode.value;
    result.device = read_node(selected);
    result.driver.emplace(); result.driver->devnode = selected;
    if (result.mapping.interface_path.observed() && *result.mapping.interface_path.value == endpoint &&
        result.mapping.cleanup_errors.empty()) {
      // Four fixed properties, queried independently and charged to the same
      // original time/call/byte budget. A failed field cannot borrow a parent's.
      const std::pair<Property, Observation<std::wstring>*> fields[] = {
        {Property::DriverProvider, &result.driver->provider},
        {Property::DriverService, &result.driver->service},
        {Property::DriverVersion, &result.driver->version},
        {Property::DriverInfPath, &result.driver->inf_path},
      };
      for (const auto& field : fields) {
        const auto raw = read_property(selected, field.first);
        *field.second = raw.observed() ? decode_driver_string(*raw.value, limits.max_instance_chars) :
            Observation<std::wstring>::missing(raw.unavailable);
      }
    }
    before_call(); result.observed_root = api.root_node();
    std::set<DevNode> seen{selected};
    DevNode current = selected;
    while (true) {
      if (result.observed_root.observed() && current == *result.observed_root.value) {
        result.chain_end = ChainEnd::ReachedObservedRoot; break;
      }
      if (result.parents.size() >= limits.max_parent_nodes) {
        result.chain_end = ChainEnd::DepthLimit; break;
      }
      before_call(); const auto parent = api.parent_node(current);
      if (!parent.observed()) {
        result.chain_end = ChainEnd::ParentUnavailable; result.chain_error = parent.unavailable; break;
      }
      if (!seen.insert(*parent.value).second) {
        result.chain_end = ChainEnd::ParentCycle; result.chain_error = invalid(Unavailable::MalformedValue); break;
      }
      current = *parent.value;
      result.parents.push_back(read_node(current));
    }
  } catch (const Stopped& stopped) {
    result.chain_error = invalid(stopped.reason);
    switch (stopped.reason) {
      case Unavailable::Cancelled: result.chain_end = ChainEnd::Cancelled; break;
      case Unavailable::Deadline: result.chain_end = ChainEnd::Deadline; break;
      case Unavailable::ClockChanged: result.chain_end = ChainEnd::ClockChanged; break;
      default: result.chain_end = ChainEnd::CallLimit; break;
    }
  }
  return result;
}

namespace {
const char* reason_name(Unavailable value) {
  switch (value) {
    case Unavailable::None: return "NONE";
    case Unavailable::NotRequested: return "NOT_REQUESTED";
    case Unavailable::ApiFailure: return "API_FAILURE";
    case Unavailable::WrongPropertyType: return "WRONG_PROPERTY_TYPE";
    case Unavailable::MalformedValue: return "MALFORMED_VALUE";
    case Unavailable::ByteLimit: return "BYTE_LIMIT";
    case Unavailable::Cancelled: return "CANCELLED";
    case Unavailable::Deadline: return "DEADLINE";
    case Unavailable::ClockChanged: return "CLOCK_CHANGED";
    case Unavailable::CallLimit: return "CALL_LIMIT";
  }
  throw std::invalid_argument("Unregistered identity error reason");
}
const char* domain_name(ErrorDomain value) {
  switch (value) {
    case ErrorDomain::None: return "NONE";
    case ErrorDomain::Win32: return "WIN32";
    case ErrorDomain::ConfigurationManager: return "CONFIGURATION_MANAGER";
    case ErrorDomain::Contract: return "CONTRACT";
  }
  throw std::invalid_argument("Unregistered identity error domain");
}
const char* chain_name(ChainEnd value) {
  switch (value) {
    case ChainEnd::NotRequested: return "NOT_REQUESTED";
    case ChainEnd::ReachedObservedRoot: return "REACHED_OBSERVED_ROOT";
    case ChainEnd::ParentUnavailable: return "PARENT_UNAVAILABLE";
    case ChainEnd::ParentCycle: return "PARENT_CYCLE";
    case ChainEnd::DepthLimit: return "DEPTH_LIMIT";
    case ChainEnd::Cancelled: return "CANCELLED";
    case ChainEnd::Deadline: return "DEADLINE";
    case ChainEnd::ClockChanged: return "CLOCK_CHANGED";
    case ChainEnd::CallLimit: return "CALL_LIMIT";
  }
  throw std::invalid_argument("Unregistered parent chain termination");
}
std::string json_quoted(const std::string& value) {
  std::ostringstream out;
  out << '"';
  for (unsigned char code : value) {
    if (code == '"' || code == '\\') out << '\\' << static_cast<char>(code);
    else if (code < 32) out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<unsigned>(code);
    else out << static_cast<char>(code);
  }
  out << '"';
  return out.str();
}
std::string quoted_utf16(const std::wstring& value) {
  if (!valid_text(value, 4096)) throw std::invalid_argument("Invalid metadata text");
  std::string utf8;
  for (std::size_t i = 0; i < value.size(); ++i) {
    std::uint32_t code = static_cast<std::uint16_t>(value[i]);
    if (code >= 0xd800 && code <= 0xdbff) {
      code = 0x10000 + ((code - 0xd800) << 10) + (static_cast<std::uint16_t>(value[++i]) - 0xdc00);
    }
    if (code < 0x80) utf8.push_back(static_cast<char>(code));
    else if (code < 0x800) {
      utf8.push_back(static_cast<char>(0xc0 | (code >> 6)));
      utf8.push_back(static_cast<char>(0x80 | (code & 63)));
    } else if (code < 0x10000) {
      utf8.push_back(static_cast<char>(0xe0 | (code >> 12)));
      utf8.push_back(static_cast<char>(0x80 | ((code >> 6) & 63)));
      utf8.push_back(static_cast<char>(0x80 | (code & 63)));
    } else {
      utf8.push_back(static_cast<char>(0xf0 | (code >> 18)));
      utf8.push_back(static_cast<char>(0x80 | ((code >> 12) & 63)));
      utf8.push_back(static_cast<char>(0x80 | ((code >> 6) & 63)));
      utf8.push_back(static_cast<char>(0x80 | (code & 63)));
    }
  }
  return json_quoted(utf8);
}
std::string error_json(const Error& error) {
  return "{\"reason\":" + json_quoted(reason_name(error.reason)) + ",\"domain\":" +
      json_quoted(domain_name(error.domain)) + ",\"native_code\":" + std::to_string(error.native_code) + '}';
}
std::string value_json(const DevNode& value) { return std::to_string(value); }
std::string value_json(const std::wstring& value) { return quoted_utf16(value); }
std::string value_json(const ContainerGuid& guid) {
  std::ostringstream out;
  out << std::hex << std::setfill('0') << std::setw(8) << guid.data1 << '-'
      << std::setw(4) << guid.data2 << '-' << std::setw(4) << guid.data3 << '-';
  for (std::size_t i = 0; i < guid.data4.size(); ++i) {
    if (i == 2) out << '-';
    out << std::setw(2) << static_cast<unsigned>(guid.data4[i]);
  }
  return json_quoted(out.str());
}
std::string value_json(const std::vector<std::wstring>& paths) {
  std::string out = "[";
  for (std::size_t i = 0; i < paths.size(); ++i) {
    if (i) out += ',';
    out += quoted_utf16(paths[i]);
  }
  return out + ']';
}
template <class T> std::string observation_json(const Observation<T>& value) {
  return "{\"availability\":" + json_quoted(value.observed() ? "OBSERVED" : "UNAVAILABLE") +
      ",\"value\":" + (value.observed() ? value_json(*value.value) : "null") +
      ",\"error\":" + error_json(value.unavailable) + '}';
}
std::string node_json(const NodeMetadata& node) {
  return "{\"devnode\":" + std::to_string(node.devnode) + ",\"instance_id\":" +
      observation_json(node.instance_id) + ",\"container_id\":" + observation_json(node.container_id) +
      ",\"location_paths\":" + observation_json(node.location_paths) + '}';
}
std::string driver_json(const DriverMetadata& driver) {
  return "{\"devnode\":" + std::to_string(driver.devnode) + ",\"provider\":" + observation_json(driver.provider) +
      ",\"service\":" + observation_json(driver.service) + ",\"version\":" + observation_json(driver.version) +
      ",\"inf_path\":" + observation_json(driver.inf_path) + '}';
}
} // namespace

std::string serialize_identity_metadata(const IdentityMetadata& metadata, const Limits& limits) {
  std::ostringstream out;
  out << "{\"schema\":\"rocell.windows_camera_identity.v2\",\"status\":\"METADATA_ONLY\","
      << "\"requested_endpoint\":" << quoted_utf16(metadata.requested_endpoint)
      << ",\"mapping\":{\"devnode\":" << observation_json(metadata.mapping.devnode)
      << ",\"interface_path\":" << observation_json(metadata.mapping.interface_path) << ",\"cleanup_errors\":[";
  for (std::size_t i = 0; i < metadata.mapping.cleanup_errors.size(); ++i) {
    if (i) out << ',';
    out << error_json(metadata.mapping.cleanup_errors[i]);
  }
  out << "]},\"device\":" << (metadata.device ? node_json(*metadata.device) : "null")
      << ",\"driver\":" << (metadata.driver ? driver_json(*metadata.driver) : "null") << ",\"parents\":[";
  for (std::size_t i = 0; i < metadata.parents.size(); ++i) {
    if (i) out << ',';
    out << node_json(metadata.parents[i]);
  }
  out << "],\"observed_root\":" << observation_json(metadata.observed_root)
      << ",\"chain_end\":" << json_quoted(chain_name(metadata.chain_end))
      << ",\"chain_error\":" << error_json(metadata.chain_error)
      << ",\"api_calls\":" << metadata.api_calls
      << ",\"observed_property_bytes\":" << metadata.observed_property_bytes
      << ",\"limits\":{\"max_parent_nodes\":" << limits.max_parent_nodes
      << ",\"max_property_bytes\":" << limits.max_property_bytes
      << ",\"max_total_property_bytes\":" << limits.max_total_property_bytes
      << ",\"max_instance_chars\":" << limits.max_instance_chars
      << ",\"max_location_paths\":" << limits.max_location_paths
      << ",\"duration_ms\":" << limits.duration_ms << '}'
      << ",\"provenance\":\"WINDOWS_SETUPAPI_CONFIGURATION_MANAGER_METADATA\","
      << "\"camera_activation_count\":0,\"physical_authority\":false}";
  const auto result = out.str();
  if (result.size() > 256 * 1024) throw std::runtime_error("Identity metadata receipt exceeded byte budget");
  return result;
}
} // namespace rocell::identity
