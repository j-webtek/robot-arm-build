#pragma once
// Separate v2 request codec. Parsing is data validation, never device admission.
#include "admission_protocol.h"
#include "camera_activation_identity.h"

namespace rocell::activation_protocol {
enum class Purpose { Probe, Capture };
struct ExpectedIdentity {
  activation_identity::Expected traits;
  std::string original_identity_sha256;
  std::string payload_sha256;
};
struct Request {
  admission::Request admission;
  ExpectedIdentity identity;
  Purpose purpose;
};

ExpectedIdentity parse_expected_identity(const std::string& payload);
Request parse_request(const std::string& payload, const std::string& expected_hash,
                      Purpose purpose);
}  // namespace rocell::activation_protocol
