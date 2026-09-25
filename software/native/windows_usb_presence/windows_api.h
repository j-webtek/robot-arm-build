#pragma once
#include "presence.h"
namespace rocell::usb_presence {
class WindowsPresenceApi final : public PresenceApi {
public:
  ApiResult size(const std::string &) override;
  ApiResult list(const std::string &, std::uint32_t) override;
};
} // namespace rocell::usb_presence
