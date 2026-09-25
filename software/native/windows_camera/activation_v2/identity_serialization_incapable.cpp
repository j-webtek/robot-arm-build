// Test-only exact extraction from installed identity_metadata.cpp.
// No resolver or Windows device adapter is compiled in this translation unit.
// Tests compare both extracted regions to the original to prevent codec drift.
#include "identity_metadata.h"
#include <iomanip>
#include <sstream>
#include <stdexcept>
namespace rocell::identity {
namespace {
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
