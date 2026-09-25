// Inherited-pipe admission only: no MF/COM/device implementation is linked.
#include "capture_admission_entry.h"
#include <filesystem>
#include <iostream>
#include <stdexcept>

int wmain(int argc, wchar_t** argv) {
  try {
    if (argc != 4 || std::wstring(argv[1]) != L"--owned-capture")
      throw std::runtime_error("INCAPABLE_CAPTURE_ARGUMENTS");
    const auto state = rocell::capture_admission::admit_owned_capture(
        std::vector<std::wstring>(argv + 2, argv + argc));
    const auto arguments = rocell::capture_admission::capture_arguments(state, std::filesystem::current_path().wstring());
    if (!state.admitted() || arguments.front() != L"capture") throw std::runtime_error("NOT_ADMITTED");
    std::cout << "{\"admitted\":true,\"challenge_sha256\":\"" << state.challenge_hash()
      << "\",\"child_pid\":" << state.pid() << ",\"device_effects\":0,\"request_sha256\":\"" << state.request().hash
      << "\",\"schema\":\"rocell.native_camera_capture_admission_only_test.v1\"}\n";
    return 0;
  } catch (const std::exception& error) { std::cerr << error.what() << '\n'; return 2; }
}
