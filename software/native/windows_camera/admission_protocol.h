#pragma once
#include <cstdint>
#include <map>
#include <string>

// No COM/MF/device dependencies. This narrow flat-JSON codec is shared with a
// separately linked incapable test target, never a runtime admission bypass.
namespace rocell::admission {
inline constexpr std::size_t request_limit = 16384;
inline constexpr std::size_t handshake_limit = 1024;
struct Value { std::string text; bool number = false; };
using Fields = std::map<std::string, Value>;
std::string sha256(const std::string& bytes);
Fields parse_flat(const std::string& canonical_json, std::size_t maximum);
struct Request {
  Fields fields;
  std::string hash;
  std::string endpoint() const { return fields.at("endpoint").text; }
  std::string permit() const { return fields.at("permit_sha256").text; }
};
Request parse_request(const std::string& payload, const std::string& expected_hash);
std::string ready_json(const Request&, std::uint32_t child_pid, const std::string& challenge);
void validate_release(const std::string& payload, const Request&, std::uint32_t child_pid,
                      const std::string& challenge);
// Refuses a second acceptance even after the first release was malformed.
class AdmissionState {
 public:
  AdmissionState(Request request, std::uint32_t pid, std::string challenge);
  std::string ready() const;
  void accept(const std::string& release, bool eof);
  bool admitted() const noexcept { return admitted_; }
  const Request& request() const { return request_; }
  std::uint32_t pid() const { return pid_; }
  std::string challenge_hash() const;
 private:
  Request request_;
  std::uint32_t pid_;
  std::string challenge_;
  bool attempted_ = false, admitted_ = false;
};
}
