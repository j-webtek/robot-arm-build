#include "camera_activation_entry.h"

// clang-format off
// bcrypt's public Windows types require windows.h first.
#include <windows.h>
#include <bcrypt.h>
// clang-format on

#include <array>
#include <limits>

#include "capture_admission_protocol.h"

namespace rocell::activation_entry {
namespace {
void need(bool ok, const char* code) {
  if (!ok) throw std::runtime_error(code);
}
void alive(std::uint64_t deadline) {
  need(GetTickCount64() < deadline, "ACTIVATION_ADMISSION_DEADLINE");
}
std::string line(HANDLE input, std::size_t maximum, std::uint64_t deadline) {
  std::string result;
  while (result.size() < maximum) {
    alive(deadline);
    DWORD available = 0;
    need(PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr) != FALSE,
         "ACTIVATION_ADMISSION_PIPE_EOF");
    if (!available) {
      Sleep(1);
      continue;
    }
    char value;
    DWORD read = 0;
    need(ReadFile(input, &value, 1, &read, nullptr) && read == 1,
         "ACTIVATION_ADMISSION_READ_FAILED");
    if (value == '\n') return result;
    result += value;
  }
  throw std::runtime_error("ACTIVATION_ADMISSION_LINE_LIMIT");
}
void eof(HANDLE input, std::uint64_t deadline) {
  while (true) {
    alive(deadline);
    DWORD available = 0;
    if (!PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr)) {
      need(GetLastError() == ERROR_BROKEN_PIPE, "ACTIVATION_ADMISSION_EOF_FAILED");
      return;
    }
    need(available == 0, "ACTIVATION_ADMISSION_EXTRA_INPUT");
    Sleep(1);
  }
}
std::wstring wide(const std::string& value) {
  need(!value.empty() && value.size() <= 4096, "ACTIVATION_ARGUMENT_BOUNDS");
  const auto n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                                     static_cast<int>(value.size()), nullptr, 0);
  need(n > 0, "ACTIVATION_ARGUMENT_UTF8");
  std::wstring result(static_cast<std::size_t>(n), L'\0');
  need(MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, value.data(),
                           static_cast<int>(value.size()), result.data(), n) == n,
       "ACTIVATION_ARGUMENT_UTF8");
  return result;
}
}  // namespace

Admitted admit(const std::vector<std::wstring>& arguments,
               activation_protocol::Purpose purpose) {
  need(
      arguments.size() == 2 && arguments[0] == L"--request-sha256" && arguments[1].size() == 64,
      "ACTIVATION_OWNED_ARGUMENTS");
  std::string hash;
  for (wchar_t c : arguments[1]) {
    need((c >= L'0' && c <= L'9') || (c >= L'a' && c <= L'f'), "ACTIVATION_OWNED_HASH");
    hash += static_cast<char>(c);
  }
  need(purpose == activation_protocol::Purpose::Probe ||
           purpose == activation_protocol::Purpose::Capture,
       "ACTIVATION_OWNED_PURPOSE");
  const auto budget = purpose == activation_protocol::Purpose::Probe ? 2000ULL : 5000ULL;
  const auto deadline = GetTickCount64() + budget;
  const HANDLE input = GetStdHandle(STD_INPUT_HANDLE), output = GetStdHandle(STD_OUTPUT_HANDLE);
  need(input && input != INVALID_HANDLE_VALUE && output && output != INVALID_HANDLE_VALUE &&
           GetFileType(input) == FILE_TYPE_PIPE && GetFileType(output) == FILE_TYPE_PIPE,
       "ACTIVATION_INHERITED_PIPES_REQUIRED");
  auto request = activation_protocol::parse_request(
      line(input, admission::request_limit, deadline), hash, purpose);
  std::array<unsigned char, 32> random{};
  need(BCryptGenRandom(nullptr, random.data(), static_cast<ULONG>(random.size()),
                       BCRYPT_USE_SYSTEM_PREFERRED_RNG) >= 0,
       "ACTIVATION_CHALLENGE_ENTROPY_FAILED");
  constexpr char digits[] = "0123456789abcdef";
  std::string challenge;
  for (const auto byte : random) {
    challenge += digits[byte >> 4];
    challenge += digits[byte & 15];
  }
  admission::AdmissionState state(std::move(request.admission), GetCurrentProcessId(),
                                  std::move(challenge));
  const auto ready = state.ready() + '\n';
  DWORD written = 0;
  alive(deadline);
  need(WriteFile(output, ready.data(), static_cast<DWORD>(ready.size()), &written, nullptr) &&
           written == ready.size(),
       "ACTIVATION_READY_WRITE_FAILED");
  const auto release = line(input, admission::handshake_limit, deadline);
  eof(input, deadline);
  state.accept(release, true);
  alive(deadline);
  // One native deadline starts after accepted RELEASE + EOF, before startup,
  // directory inspection, metadata resolution or activation. It never renews.
  const auto started = GetTickCount64();
  need(started <= std::numeric_limits<std::uint64_t>::max() - 5000,
       "ACTIVATION_CLOCK_OVERFLOW");
  return {std::move(state), std::move(request.identity), purpose, started, started + 5000};
}

std::vector<std::wstring> operation_arguments(const Admitted& admitted,
                                              const std::wstring& cwd) {
  need(admitted.state.admitted(), "ACTIVATION_ADMISSION_REQUIRED");
  const auto& request = admitted.state.request();
  if (admitted.purpose == activation_protocol::Purpose::Probe)
    return {L"probe", L"--endpoint", admitted.identity.traits.endpoint, L"--max-ms", L"5000"};
  need(admitted.purpose == activation_protocol::Purpose::Capture,
       "ACTIVATION_ARGUMENT_PURPOSE");
  const auto settings =
      capture_admission::parse_capture_settings(request.fields.at("capture_json").text);
  const auto output = wide(settings.output_directory);
  need(!cwd.empty() && cwd.back() != L'\\' &&
           output == cwd + L"\\capture-" + wide(request.fields.at("attempt_id").text),
       "ACTIVATION_PRIVATE_DIRECTORY_BINDING");
  std::vector<std::wstring> result{L"capture",
                                   L"--endpoint",
                                   admitted.identity.traits.endpoint,
                                   L"--max-ms",
                                   L"5000",
                                   L"--width",
                                   std::to_wstring(settings.width),
                                   L"--height",
                                   std::to_wstring(settings.height),
                                   L"--fps-n",
                                   std::to_wstring(settings.fps_numerator),
                                   L"--fps-d",
                                   std::to_wstring(settings.fps_denominator),
                                   L"--frames",
                                   std::to_wstring(settings.frame_count),
                                   L"--frame-bytes",
                                   std::to_wstring(settings.max_frame_bytes),
                                   L"--total-bytes",
                                   std::to_wstring(settings.max_total_bytes),
                                   L"--output",
                                   output};
  if (!settings.controls.empty()) {
    result.push_back(L"--controls");
    result.push_back(wide(settings.controls));
  }
  return result;
}

}  // namespace rocell::activation_entry
