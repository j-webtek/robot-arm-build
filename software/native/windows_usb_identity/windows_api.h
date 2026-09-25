#pragma once
#include "observation.h"
#include <memory>
namespace rocell::usb_identity {
// Inert constructor. Only main.cpp after release+EOF constructs this adapter.
class WindowsUsbIdentityApi final : public UsbIdentityApi {
public:
  WindowsUsbIdentityApi();
  ~WindowsUsbIdentityApi();
  Result call(const Input &) override;

private:
  struct State;
  std::unique_ptr<State> state;
};
} // namespace rocell::usb_identity
