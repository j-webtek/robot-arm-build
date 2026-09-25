#include "admission_protocol.h"
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <limits>
#include <set>
#include <stdexcept>
#include <vector>

namespace rocell::admission {
namespace {
void need(bool value, const char* reason) { if (!value) throw std::runtime_error(reason); }
bool hexhash(const std::string& s) {
  if (s.size() != 64) return false;
  for (const char c : s) if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'))) return false;
  return true;
}
bool identifier(const std::string& s) {
  if (s.empty() || s.size() > 96) return false;
  for (std::size_t i = 0; i < s.size(); ++i) {
    const char c = s[i];
    if ((c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || (c >= '0' && c <= '9')) continue;
    if (i && (c == '_' || c == '.' || c == '-')) continue;
    return false;
  }
  return true;
}
std::string quote(const std::string& s) {
  std::string out = "\"";
  for (const char c : s) {
    need(c >= 32 && c < 127, "ASCII_OUTPUT_REQUIRED");
    if (c == '\\' || c == '"') out += '\\';
    out += c;
  }
  return out + '"';
}
void append_utf8(std::string& out, std::uint32_t cp) {
  if (cp < 0x800) { out += static_cast<char>(0xc0 | (cp >> 6)); out += static_cast<char>(0x80 | (cp & 63)); }
  else if (cp < 0x10000) { out += static_cast<char>(0xe0 | (cp >> 12)); out += static_cast<char>(0x80 | ((cp >> 6) & 63)); out += static_cast<char>(0x80 | (cp & 63)); }
  else { out += static_cast<char>(0xf0 | (cp >> 18)); out += static_cast<char>(0x80 | ((cp >> 12) & 63)); out += static_cast<char>(0x80 | ((cp >> 6) & 63)); out += static_cast<char>(0x80 | (cp & 63)); }
}
class Parser {
 public:
  explicit Parser(const std::string& input) : s(input) {}
  char take() { need(i < s.size(), "TRUNCATED_JSON"); return s[i++]; }
  std::uint32_t hex4() {
    std::uint32_t n = 0;
    for (unsigned j = 0; j < 4; ++j) {
      const char c = take();
      need((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f'), "CANONICAL_HEX_REQUIRED");
      n = n * 16 + static_cast<unsigned>(c <= '9' ? c - '0' : c - 'a' + 10);
    }
    return n;
  }
  std::string string() {
    need(take() == '"', "STRING_REQUIRED");
    std::string out;
    while (true) {
      const char c = take();
      if (c == '"') return out;
      need(c >= 32 && c < 127, "CANONICAL_ASCII_JSON_REQUIRED");
      if (c != '\\') { out += c; continue; }
      const char escaped = take();
      if (escaped == '\\' || escaped == '"') { out += escaped; continue; }
      need(escaped == 'u', "CONTROL_OR_NONCANONICAL_ESCAPE");
      auto cp = hex4();
      need(cp >= 128, "NONCANONICAL_UNICODE_ESCAPE");
      if (cp >= 0xd800 && cp <= 0xdbff) {
        need(take() == '\\' && take() == 'u', "MISSING_LOW_SURROGATE");
        const auto low = hex4(); need(low >= 0xdc00 && low <= 0xdfff, "INVALID_LOW_SURROGATE");
        cp = 0x10000 + ((cp - 0xd800) << 10) + low - 0xdc00;
      } else need(cp < 0xdc00 || cp > 0xdfff, "UNPAIRED_SURROGATE");
      append_utf8(out, cp);
    }
  }
  Fields object() {
    need(take() == '{', "FLAT_OBJECT_REQUIRED");
    Fields result; std::string previous;
    while (true) {
      const auto key = string();
      need(key.size() <= 64 && (result.empty() || key > previous), "SORTED_UNIQUE_KEYS_REQUIRED");
      previous = key; need(take() == ':', "JSON_COLON");
      Value value;
      if (i < s.size() && s[i] == '"') value.text = string();
      else {
        value.number = true;
        while (i < s.size() && s[i] >= '0' && s[i] <= '9') value.text += s[i++];
        need(!value.text.empty() && value.text.size() <= 10 && (value.text.size() == 1 || value.text[0] != '0'), "BOUNDED_INTEGER_REQUIRED");
      }
      result.emplace(key, value); need(result.size() <= 16, "FIELD_COUNT_LIMIT");
      const char delimiter = take();
      if (delimiter == '}') break;
      need(delimiter == ',', "JSON_DELIMITER");
    }
    need(i == s.size(), "TRAILING_JSON"); return result;
  }
 private:
  const std::string& s;
  std::size_t i = 0;
};
void exact(const Fields& fields, const std::set<std::string>& names) {
  need(fields.size() == names.size(), "FIELD_SET");
  for (const auto& [name, value] : fields) { (void)value; need(names.count(name) == 1, "UNKNOWN_FIELD"); }
}
std::string str(const Fields& f, const std::string& key) { const auto& v = f.at(key); need(!v.number, "STRING_FIELD_REQUIRED"); return v.text; }
}

std::string sha256(const std::string& bytes) {
  need(bytes.size() <= 256 * 1024, "HASH_BYTE_LIMIT");
  BCRYPT_ALG_HANDLE algorithm = nullptr; BCRYPT_HASH_HANDLE hash = nullptr;
  need(BCryptOpenAlgorithmProvider(&algorithm, BCRYPT_SHA256_ALGORITHM, nullptr, 0) >= 0, "SHA_OPEN");
  std::array<unsigned char, 32> output{};
  std::vector<unsigned char> object;
  try {
    DWORD size = 0, returned = 0;
    need(BCryptGetProperty(algorithm, BCRYPT_OBJECT_LENGTH, reinterpret_cast<PUCHAR>(&size), sizeof(size), &returned, 0) >= 0 && size <= 65536, "SHA_OBJECT");
    object.resize(size);
    need(BCryptCreateHash(algorithm, &hash, object.data(), size, nullptr, 0, 0) >= 0, "SHA_CREATE");
    need(BCryptHashData(hash, reinterpret_cast<PUCHAR>(const_cast<char*>(bytes.data())), static_cast<ULONG>(bytes.size()), 0) >= 0, "SHA_DATA");
    need(BCryptFinishHash(hash, output.data(), static_cast<ULONG>(output.size()), 0) >= 0, "SHA_FINISH");
    BCryptDestroyHash(hash); hash = nullptr;
  } catch (...) { if (hash) BCryptDestroyHash(hash); BCryptCloseAlgorithmProvider(algorithm, 0); throw; }
  BCryptCloseAlgorithmProvider(algorithm, 0);
  static constexpr char digits[] = "0123456789abcdef";
  std::string result; for (auto b : output) { result += digits[b >> 4]; result += digits[b & 15]; } return result;
}
Fields parse_flat(const std::string& payload, std::size_t maximum) {
  need(!payload.empty() && payload.size() < maximum, "MESSAGE_BYTE_LIMIT"); return Parser(payload).object();
}
Request parse_request(const std::string& payload, const std::string& expected_hash) {
  need(hexhash(expected_hash) && sha256(payload) == expected_hash, "REQUEST_HASH");
  auto f = parse_flat(payload, request_limit);
  exact(f, {"schema", "attempt_id", "session_id", "source_sha256", "operation_sha256", "selected_identity_sha256", "endpoint", "endpoint_sha256", "helper_sha256", "runtime_registration_sha256", "camera_request_sha256", "permit_sha256", "native_duration_ms", "admission_timeout_ms"});
  need(str(f, "schema") == "rocell.native_camera_admission_request.v1", "REQUEST_SCHEMA");
  need(identifier(str(f, "attempt_id")) && identifier(str(f, "session_id")), "REQUEST_ID");
  for (const auto& key : {"source_sha256", "operation_sha256", "selected_identity_sha256", "endpoint_sha256", "helper_sha256", "runtime_registration_sha256", "camera_request_sha256", "permit_sha256"}) need(hexhash(str(f, key)), "REQUEST_DIGEST");
  const auto endpoint = str(f, "endpoint");
  need(!endpoint.empty() && endpoint.size() <= 4096 && sha256(endpoint) == str(f, "endpoint_sha256"), "ENDPOINT_BINDING");
  need(f.at("native_duration_ms").number && f.at("native_duration_ms").text == "5000" && f.at("admission_timeout_ms").number && f.at("admission_timeout_ms").text == "2000", "PROBE_BUDGET");
  return {std::move(f), expected_hash};
}
std::string ready_json(const Request& r, std::uint32_t pid, const std::string& challenge) {
  need(pid != 0 && hexhash(challenge), "CHILD_CHALLENGE");
  return "{\"challenge\":" + quote(challenge) + ",\"child_pid\":" + std::to_string(pid) + ",\"request_sha256\":" + quote(r.hash) + ",\"schema\":\"rocell.native_camera_admission_ready.v1\"}";
}
void validate_release(const std::string& payload, const Request& r, std::uint32_t pid, const std::string& challenge) {
  const auto f = parse_flat(payload, handshake_limit);
  exact(f, {"schema", "request_sha256", "child_pid", "challenge_sha256", "permit_sha256"});
  need(str(f, "schema") == "rocell.native_camera_admission_release.v1" && str(f, "request_sha256") == r.hash && str(f, "permit_sha256") == r.permit() && str(f, "challenge_sha256") == sha256(challenge), "RELEASE_BINDING");
  need(f.at("child_pid").number && f.at("child_pid").text == std::to_string(pid), "RELEASE_CHILD_PID");
}
AdmissionState::AdmissionState(Request r, std::uint32_t pid, std::string challenge) : request_(std::move(r)), pid_(pid), challenge_(std::move(challenge)) { (void)ready(); }
std::string AdmissionState::ready() const { return ready_json(request_, pid_, challenge_); }
std::string AdmissionState::challenge_hash() const { return sha256(challenge_); }
void AdmissionState::accept(const std::string& release, bool eof) {
  need(!attempted_, "RELEASE_ALREADY_ATTEMPTED"); attempted_ = true;
  validate_release(release, request_, pid_, challenge_); need(eof, "RELEASE_EOF_REQUIRED"); admitted_ = true;
}
}
