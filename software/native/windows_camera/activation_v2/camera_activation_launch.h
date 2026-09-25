#pragma once
// Fixed-purpose argv validation shared by the worker and incapable tests.
// No pipes, files, Win32 APIs or device libraries are used by this function.
#include <string>
#include <vector>

#include "camera_activation_protocol.h"

namespace rocell::activation_launch {
inline bool accepts(const std::vector<std::wstring>& arguments,
                    activation_protocol::Purpose purpose) {
  using Purpose = activation_protocol::Purpose;
  if (purpose != Purpose::Probe && purpose != Purpose::Capture) return false;
  if (arguments.size() != 3 || arguments[1] != L"--request-sha256" ||
      arguments[2].size() != 64) return false;
  const auto flag = purpose == Purpose::Probe ? L"--owned-probe-v2" : L"--owned-capture-v2";
  if (arguments[0] != flag) return false;
  for (const auto c : arguments[2]) {
    if (!((c >= L'0' && c <= L'9') || (c >= L'a' && c <= L'f'))) return false;
  }
  return true;
}
}  // namespace rocell::activation_launch
