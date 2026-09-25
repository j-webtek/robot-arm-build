#pragma once
#include <cstdint>
#include <map>
#include <string>
#include <vector>

namespace rocell::usb_identity {
inline constexpr std::size_t request_limit = 16384, handshake_limit = 1024;
struct Value {
  std::string text;
  bool number = false;
};
using Fields = std::map<std::string, Value>;
std::string sha256(const std::string &);
Fields parse_flat(const std::string &, std::size_t maximum);
struct Request {
  Fields fields;
  std::string hash;
  std::string endpoint() const { return fields.at("endpoint").text; }
  std::string expected_instance() const {
    return fields.at("expected_device_instance_id").text;
  }
  std::string permit() const { return fields.at("permit_sha256").text; }
};
Request parse_request(const std::string &, const std::string &expected_hash);
std::string ready_json(const Request &, std::uint32_t, const std::string &);
void validate_release(const std::string &, const Request &, std::uint32_t,
                      const std::string &);
class AdmissionState {
public:
  AdmissionState(Request, std::uint32_t, std::string);
  std::string ready() const;
  void accept(const std::string &, bool eof);
  bool admitted() const { return admitted_; }
  const Request &request() const { return request_; }
  std::uint32_t pid() const { return pid_; }
  std::string challenge_hash() const;

private:
  Request request_;
  std::uint32_t pid_;
  std::string challenge_;
  bool attempted_ = false, admitted_ = false;
};
AdmissionState admit_owned_usb(const std::vector<std::wstring> &);
std::string wrap_result(const AdmissionState &, const std::string &native_json);
} // namespace rocell::usb_identity
