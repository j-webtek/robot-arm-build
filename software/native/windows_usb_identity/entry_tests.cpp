#include "fake_api.h"
#include <iostream>
#include <windows.h>
// Separate process target: no WindowsUsbIdentityApi, SetupAPI or device I/O
// code.
int wmain(int argc, wchar_t **argv) {
  using namespace rocell::usb_identity;
  bool admitted = false;
  try {
    if (argc != 4 || std::wstring(argv[1]) != L"--owned-usb-identity")
      return 2;
    auto gate = admit_owned_usb({argv[2], argv[3]});
    if (!gate.admitted())
      return 2;
    admitted = true;
    test::FakeApi api;
    auto observation = observe_usb_identity(
        api, gate.request(), Limits{}, [] { return false; },
        [] { return std::uint64_t(0); });
    auto output = wrap_result(gate, serialize_observation(observation)) + '\n';
    DWORD n = 0;
    if (!WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), output.data(),
                   static_cast<DWORD>(output.size()), &n, nullptr) ||
        n != output.size())
      return 3;
    return observation.outcome == "OBSERVED" ? 0 : 1;
  } catch (...) {
    return admitted ? 3 : 2;
  }
}
