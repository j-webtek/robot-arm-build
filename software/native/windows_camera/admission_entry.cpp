#include "admission_entry.h"
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <stdexcept>

namespace rocell::admission {
namespace {
void need(bool value, const char* code) { if (!value) throw std::runtime_error(code); }
void alive(ULONGLONG deadline) { need(GetTickCount64() < deadline, "ADMISSION_DEADLINE"); }
std::string line(HANDLE input, std::size_t maximum, ULONGLONG deadline) {
  std::string out;
  while (out.size() < maximum) {
    alive(deadline); DWORD available = 0;
    need(PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr) != FALSE, "ADMISSION_PIPE_EOF");
    if (!available) { Sleep(1); continue; }
    char value; DWORD read = 0;
    need(ReadFile(input, &value, 1, &read, nullptr) && read == 1, "ADMISSION_READ_FAILED");
    if (value == '\n') return out;
    out += value;
  }
  throw std::runtime_error("ADMISSION_LINE_LIMIT");
}
void eof(HANDLE input, ULONGLONG deadline) {
  while (true) {
    alive(deadline); DWORD available = 0;
    if (!PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr)) {
      need(GetLastError() == ERROR_BROKEN_PIPE, "ADMISSION_EOF_FAILED"); return;
    }
    need(available == 0, "ADMISSION_EXTRA_INPUT"); Sleep(1);
  }
}
}
AdmissionState admit_owned_probe(const std::vector<std::wstring>& arguments) {
  need(arguments.size() == 2 && arguments[0] == L"--request-sha256" && arguments[1].size() == 64, "OWNED_PROBE_ARGUMENTS");
  std::string hash;
  for (const wchar_t c : arguments[1]) {
    need(c >= L'0' && c <= L'z', "ASCII_REQUEST_HASH_REQUIRED");
    hash += static_cast<char>(c);
  }
  const auto deadline = GetTickCount64() + 2000;
  HANDLE input = GetStdHandle(STD_INPUT_HANDLE), output = GetStdHandle(STD_OUTPUT_HANDLE);
  need(input && input != INVALID_HANDLE_VALUE && output && output != INVALID_HANDLE_VALUE && GetFileType(input) == FILE_TYPE_PIPE && GetFileType(output) == FILE_TYPE_PIPE, "INHERITED_PIPE_CHANNEL_REQUIRED");
  auto request = parse_request(line(input, request_limit, deadline), hash);
  std::array<unsigned char, 32> random{};
  need(BCryptGenRandom(nullptr, random.data(), static_cast<ULONG>(random.size()), BCRYPT_USE_SYSTEM_PREFERRED_RNG) >= 0, "CHILD_CHALLENGE_ENTROPY_FAILED");
  static constexpr char digits[] = "0123456789abcdef";
  std::string challenge; for (const auto b : random) { challenge += digits[b >> 4]; challenge += digits[b & 15]; }
  AdmissionState state(std::move(request), GetCurrentProcessId(), std::move(challenge));
  const auto ready = state.ready() + '\n'; DWORD written = 0;
  alive(deadline);
  need(WriteFile(output, ready.data(), static_cast<DWORD>(ready.size()), &written, nullptr) && written == ready.size(), "READY_WRITE_FAILED");
  const auto release = line(input, handshake_limit, deadline);
  eof(input, deadline);
  state.accept(release, true); alive(deadline);
  return state;
}
std::wstring endpoint_wide(const AdmissionState& admission) {
  need(admission.admitted(), "NATIVE_ADMISSION_REQUIRED");
  const auto endpoint = admission.request().endpoint();
  const int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, endpoint.data(), static_cast<int>(endpoint.size()), nullptr, 0);
  need(n > 0 && n <= 4096, "ENDPOINT_UTF8_INVALID"); std::wstring out(static_cast<std::size_t>(n), L'\0');
  need(MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, endpoint.data(), static_cast<int>(endpoint.size()), out.data(), n) == n, "ENDPOINT_UTF8_FAILED"); return out;
}
std::string wrap_native_result(const AdmissionState& a, const std::string& native) {
  need(a.admitted(), "NATIVE_ADMISSION_REQUIRED");
  return "{\"schema\":\"rocell.owned_native_camera_result.v1\",\"request_sha256\":\"" + a.request().hash + "\",\"child_pid\":" + std::to_string(a.pid()) + ",\"challenge_sha256\":\"" + a.challenge_hash() + "\",\"permit_sha256\":\"" + a.request().permit() + "\",\"native_receipt\":" + native + '}';
}
}
