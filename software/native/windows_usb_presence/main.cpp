#include "windows_api.h"
int wmain(int argc, wchar_t **argv) {
  using namespace rocell::usb_presence;
  bool released = false;
  try {
    if (argc != 4 || std::wstring(argv[1]) != L"--owned-usb-presence")
      return 2;
    auto admission = admit({argv[2], argv[3]});
    released = true;
    WindowsPresenceApi api;
    const auto result = observe(
        api, admission.request, "WINDOWS_CONFIGURATION_MANAGER",
        [] { return false; }, windows_clock);
    publish(admission, result);
    return result.outcome == "HELD" ? 1 : 0;
  } catch (...) {
    // No receipt after release means unknown API observations, never absence.
    return released ? 3 : 2;
  }
}
