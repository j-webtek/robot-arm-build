#include <iostream>
#include <stdexcept>
#include "camera_activation_launch.h"

int main() {
  using P = rocell::activation_protocol::Purpose;
  unsigned checks = 0;
  const auto check = [&](bool value) {
    ++checks;
    if (!value) throw std::runtime_error("FIXED_PURPOSE_LAUNCH_ASSERTION");
  };
  for (const auto purpose : {P::Probe, P::Capture}) {
    const auto flag = purpose == P::Probe ? L"--owned-probe-v2" : L"--owned-capture-v2";
    const std::vector<std::wstring> valid{flag, L"--request-sha256", std::wstring(64, L'a')};
    check(rocell::activation_launch::accepts(valid, purpose));
    for (const auto other : {L"inventory", L"identity", L"--self-test", L"probe", L"capture",
                             L"--owned-probe", L"--owned-capture", L"--owned-probe-v2",
                             L"--owned-capture-v2"}) {
      auto changed = valid;
      changed[0] = other;
      check(rocell::activation_launch::accepts(changed, purpose) == (changed[0] == flag));
    }
    for (const auto hash : {std::wstring(63, L'a'), std::wstring(65, L'a'),
                            std::wstring(64, L'A'), std::wstring(64, L'g'),
                            std::wstring(63, L'a') + L'\n'}) {
      auto changed = valid;
      changed[2] = hash;
      check(!rocell::activation_launch::accepts(changed, purpose));
    }
    auto changed = valid;
    changed.push_back(L"--endpoint");
    check(!rocell::activation_launch::accepts(changed, purpose));
    changed = valid;
    changed.erase(changed.begin());
    check(!rocell::activation_launch::accepts(changed, purpose));
    changed = valid;
    changed[1] = L"--endpoint";
    check(!rocell::activation_launch::accepts(changed, purpose));
    check(!rocell::activation_launch::accepts({}, purpose));
  }
  check(!rocell::activation_launch::accepts(
      {L"--owned-probe-v2", L"--request-sha256", std::wstring(64, L'a')}, static_cast<P>(99)));
  std::cout << "PASS: " << checks << " incapable fixed-purpose launch assertions\n";
}
