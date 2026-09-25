// This executable owns only inherited-pipe admission. No COM/MF/camera code is
// linked. Its explicit test completion is NOT a native or hardware receipt.
#include "admission_entry.h"
#include <iostream>
#include <stdexcept>

int wmain(int argc, wchar_t** argv) {
  try {
    if (argc != 4 || std::wstring(argv[1]) != L"--owned-probe")
      throw std::runtime_error("INCAPABLE_TEST_ARGUMENTS");
    const auto state = rocell::admission::admit_owned_probe(
        std::vector<std::wstring>(argv + 2, argv + argc));
    if (!state.admitted()) throw std::runtime_error("NOT_ADMITTED");
    std::cout << "{\"admitted\":true,\"challenge_sha256\":\""
      << state.challenge_hash() << "\",\"child_pid\":" << state.pid()
      << ",\"device_effects\":0,\"request_sha256\":\"" << state.request().hash
      << "\",\"schema\":\"rocell.native_camera_admission_only_test.v1\"}\n";
    return 0;
  } catch (const std::exception& e) {
    std::cerr << e.what() << '\n'; return 2;
  }
}
