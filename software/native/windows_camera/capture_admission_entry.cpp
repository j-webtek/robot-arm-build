#include "capture_admission_entry.h"
#include <windows.h>
#include <bcrypt.h>
#include <array>
#include <stdexcept>

namespace rocell::capture_admission {
namespace {
void need(bool value, const char* code) { if (!value) throw std::runtime_error(code); }
void alive(ULONGLONG deadline) { need(GetTickCount64() < deadline, "CAPTURE_ADMISSION_DEADLINE"); }
std::string line(HANDLE input, std::size_t maximum, ULONGLONG deadline) {
  std::string out;
  while (out.size() < maximum) {
    alive(deadline); DWORD available = 0;
    need(PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr) != FALSE, "CAPTURE_ADMISSION_PIPE_EOF");
    if (!available) { Sleep(1); continue; }
    char value; DWORD read = 0;
    need(ReadFile(input, &value, 1, &read, nullptr) && read == 1, "CAPTURE_ADMISSION_READ_FAILED");
    if (value == '\n') return out;
    out += value;
  }
  throw std::runtime_error("CAPTURE_ADMISSION_LINE_LIMIT");
}
void eof(HANDLE input, ULONGLONG deadline) {
  while (true) {
    alive(deadline); DWORD available = 0;
    if (!PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr)) {
      need(GetLastError() == ERROR_BROKEN_PIPE, "CAPTURE_ADMISSION_EOF_FAILED"); return;
    }
    need(available == 0, "CAPTURE_ADMISSION_EXTRA_INPUT"); Sleep(1);
  }
}
}
admission::AdmissionState admit_owned_capture(const std::vector<std::wstring>& arguments) {
  need(arguments.size() == 2 && arguments[0] == L"--request-sha256" && arguments[1].size() == 64, "OWNED_CAPTURE_ARGUMENTS");
  std::string hash;
  for (const wchar_t c : arguments[1]) {
    need((c >= L'0' && c <= L'9') || (c >= L'a' && c <= L'f'), "CAPTURE_REQUEST_HASH");
    hash += static_cast<char>(c);
  }
  // One original admission deadline covers REQUEST, READY, RELEASE and EOF.
  // Parsing does not renew it and the unchanged probe entry cannot borrow it.
  const auto deadline = GetTickCount64() + admission_timeout_ms;
  HANDLE input = GetStdHandle(STD_INPUT_HANDLE), output = GetStdHandle(STD_OUTPUT_HANDLE);
  need(input && input != INVALID_HANDLE_VALUE && output && output != INVALID_HANDLE_VALUE &&
    GetFileType(input) == FILE_TYPE_PIPE && GetFileType(output) == FILE_TYPE_PIPE, "CAPTURE_INHERITED_PIPE_CHANNEL_REQUIRED");
  auto request = parse_request(line(input, admission::request_limit, deadline), hash);
  std::array<unsigned char, 32> random{};
  need(BCryptGenRandom(nullptr, random.data(), static_cast<ULONG>(random.size()), BCRYPT_USE_SYSTEM_PREFERRED_RNG) >= 0, "CAPTURE_CHILD_CHALLENGE_ENTROPY_FAILED");
  static constexpr char digits[] = "0123456789abcdef";
  std::string challenge; for (const auto b : random) { challenge += digits[b >> 4]; challenge += digits[b & 15]; }
  admission::AdmissionState state(std::move(request), GetCurrentProcessId(), std::move(challenge));
  const auto ready = state.ready() + '\n'; DWORD written = 0;
  alive(deadline);
  need(WriteFile(output, ready.data(), static_cast<DWORD>(ready.size()), &written, nullptr) && written == ready.size(), "CAPTURE_READY_WRITE_FAILED");
  const auto release = line(input, admission::handshake_limit, deadline);
  eof(input, deadline); state.accept(release, true); alive(deadline);
  return state;
}
}
