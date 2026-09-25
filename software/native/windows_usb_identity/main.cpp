#include "windows_api.h"
#include <iostream>
#include <windows.h>

int wmain(int argc, wchar_t **argv) {
  using namespace rocell::usb_identity;
  bool admitted = false;
  try {
    if (argc != 4 || std::wstring(argv[1]) != L"--owned-usb-identity")
      return 2;
    auto admission = admit_owned_usb({argv[2], argv[3]});
    if (!admission.admitted())
      return 2;
    admitted = true;
    WindowsUsbIdentityApi api;
    // Parent process termination can bound waiting but cannot prove a USB
    // request completed or CloseHandle succeeded. Only this receipt reports
    // observed closes; a missing receipt remains an uncertain owned attempt.
    const auto result = observe_usb_identity(
        api, admission.request(), Limits{}, [] { return false; },
        [] { return GetTickCount64(); });
    const auto native = serialize_observation(result);
    if (native.size() > 65536)
      return 3;
    const auto wrapped = wrap_result(admission, native) + '\n';
    DWORD written = 0;
    if (!WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), wrapped.data(),
                   static_cast<DWORD>(wrapped.size()), &written, nullptr) ||
        written != wrapped.size())
      return 3;
    return result.outcome == "OBSERVED" ? 0 : 1;
  } catch (...) {
    // An exception after release is not evidence that no effect was attempted.
    return admitted ? 3 : 2;
  }
}
