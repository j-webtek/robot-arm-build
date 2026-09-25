#include "presence.h"
#include <windows.h>
#include <array>
#include <bcrypt.h>
#include <set>
#include <stdexcept>

namespace rocell::usb_presence {
namespace {
void need(bool ok, const char *reason) {
  if (!ok)
    throw std::runtime_error(reason);
}
void alive(ULONGLONG deadline) {
  need(GetTickCount64() < deadline, "ADMISSION_DEADLINE");
}
std::string line(HANDLE input, std::size_t maximum, ULONGLONG deadline) {
  std::string out;
  while (out.size() < maximum) {
    alive(deadline);
    DWORD available = 0;
    need(PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr) !=
             FALSE,
         "ADMISSION_PIPE_EOF");
    if (!available) {
      Sleep(1);
      continue;
    }
    char c;
    DWORD read = 0;
    need(ReadFile(input, &c, 1, &read, nullptr) && read == 1,
         "ADMISSION_READ_FAILED");
    if (c == '\n')
      return out;
    out += c;
  }
  throw std::runtime_error("ADMISSION_LINE_LIMIT");
}
void eof(HANDLE input, ULONGLONG deadline) {
  while (true) {
    alive(deadline);
    DWORD available = 0;
    if (!PeekNamedPipe(input, nullptr, 0, nullptr, &available, nullptr)) {
      need(GetLastError() == ERROR_BROKEN_PIPE, "ADMISSION_EOF_FAILED");
      return;
    }
    need(available == 0, "ADMISSION_EXTRA_INPUT");
    Sleep(1);
  }
}
void write(const std::string &data) {
  DWORD written = 0;
  need(WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), data.data(),
                 static_cast<DWORD>(data.size()), &written, nullptr) &&
           written == data.size(),
       "OUTPUT_WRITE_FAILED");
}
} // namespace
Moment windows_clock() {
  FILETIME time{};
  GetSystemTimePreciseAsFileTime(&time);
  ULARGE_INTEGER ticks{};
  ticks.LowPart = time.dwLowDateTime;
  ticks.HighPart = time.dwHighDateTime;
  constexpr std::uint64_t unix_epoch = 116444736000000000ULL;
  need(ticks.QuadPart >= unix_epoch, "UTC_EPOCH");
  return {GetTickCount64(), (ticks.QuadPart - unix_epoch) * 100ULL};
}
Admission admit(const std::vector<std::wstring> &args) {
  need(args.size() == 2 && args[0] == L"--request-sha256" &&
           args[1].size() == 64,
       "OWNED_ARGUMENTS");
  std::string hash;
  for (const wchar_t c : args[1]) {
    need((c >= L'0' && c <= L'9') || (c >= L'a' && c <= L'f'), "HASH_REQUIRED");
    hash += static_cast<char>(c);
  }
  HANDLE input = GetStdHandle(STD_INPUT_HANDLE),
         output = GetStdHandle(STD_OUTPUT_HANDLE);
  need(input && output && input != INVALID_HANDLE_VALUE &&
           output != INVALID_HANDLE_VALUE &&
           GetFileType(input) == FILE_TYPE_PIPE &&
           GetFileType(output) == FILE_TYPE_PIPE,
       "INHERITED_PIPE_CHANNEL_REQUIRED");
  const auto deadline = GetTickCount64() + 5000;
  auto request = parse_request(line(input, request_limit, deadline), hash);
  std::array<unsigned char, 32> random{};
  need(BCryptGenRandom(nullptr, random.data(),
                       static_cast<ULONG>(random.size()),
                       BCRYPT_USE_SYSTEM_PREFERRED_RNG) >= 0,
       "CHALLENGE_ENTROPY_FAILED");
  constexpr char digits[] = "0123456789abcdef";
  std::string challenge;
  for (const auto c : random) {
    challenge += digits[c >> 4];
    challenge += digits[c & 15];
  }
  Admission admitted{std::move(request), GetCurrentProcessId(), challenge};
  const auto &r = admitted.request;
  alive(deadline);
  write("{\"schema\":\"rocell.usb_presence_ready.v1\",\"request_sha256\":" +
        quote(r.hash) + ",\"child_pid\":" + std::to_string(admitted.pid) +
        ",\"challenge\":" + quote(challenge) + ",\"permit_sha256\":" +
        quote(r.fields.at("permit_sha256").text) + "}\n");
  const auto release =
      rocell::usb_identity::parse_flat(line(input, 1024, deadline), 1024);
  eof(input, deadline);
  const std::set<std::string> names = {"schema", "request_sha256", "child_pid",
                                       "challenge", "permit_sha256"};
  need(release.size() == names.size(), "RELEASE_FIELDS");
  for (const auto &[name, value] : release) {
    need(names.count(name) == 1 && value.number == (name == "child_pid"),
         "RELEASE_FIELDS");
  }
  need(release.at("schema").text == "rocell.usb_presence_release.v1" &&
           release.at("request_sha256").text == r.hash &&
           release.at("challenge").text == challenge &&
           release.at("permit_sha256").text ==
               r.fields.at("permit_sha256").text &&
           release.at("child_pid").text == std::to_string(admitted.pid),
       "RELEASE_BINDING");
  alive(deadline);
  return admitted;
}
void publish(const Admission &a, const Observation &o) {
  need(o.request.hash == a.request.hash, "RESULT_REQUEST_MISMATCH");
  write(
      "{\"schema\":\"rocell.owned_usb_presence_result.v1\",\"request_"
      "sha256\":" +
      quote(a.request.hash) + ",\"child_pid\":" + std::to_string(a.pid) +
      ",\"challenge_sha256\":" + quote(sha256(a.challenge)) +
      ",\"permit_sha256\":" + quote(a.request.fields.at("permit_sha256").text) +
      ",\"observation\":" + serialize(o) + "}\n");
}
} // namespace rocell::usb_presence
