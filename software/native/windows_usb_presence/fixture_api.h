#pragma once
#include "presence.h"
#include <stdexcept>
namespace rocell::usb_presence {
// Incapable adapter: no cfgmgr32, device handles, camera or serial code linked.
class FixtureApi final : public PresenceApi {
public:
  std::string scenario = "absent", target;
  std::uint32_t calls = 0, samples = 0;
  std::function<void()> on_call = [] {};
  ApiResult size(const std::string &filter) override {
    ++calls;
    on_call();
    if (scenario == "exception")
      throw std::runtime_error("MODELED_PRIVATE_DETAIL");
    if (upper_ascii(filter) != upper_ascii(device_filter(target)))
      throw std::runtime_error("FILTER_REQUIRED");
    if (scenario == "size-failed")
      return {13, 0, {}};
    if (scenario == "oversize")
      return {0, max_chars + 1, {}};
    if (scenario == "zero-size")
      return {};
    return {0, 8192, {}};
  }
  ApiResult list(const std::string &, std::uint32_t capacity) override {
    ++calls;
    ++samples;
    on_call();
    if (scenario == "list-failed" || scenario == "growth")
      return {26, 0, {}};
    ApiResult result;
    result.multi_sz.assign(capacity, static_cast<wchar_t>(0xffff));
    if (scenario == "unterminated")
      return result;
    std::vector<std::string> ids;
    if (scenario == "present" || (scenario == "changed" && samples == 1))
      ids.push_back(target);
    if (scenario == "same-model")
      ids.push_back(device_filter(target) + "\\ANOTHER_UNIT");
    if (scenario == "wrong-filter")
      ids.push_back("USB\\VID_4321&PID_8765\\UNRELATED");
    if (scenario == "duplicate")
      ids = {target, upper_ascii(target)};
    if (scenario == "many") {
      for (std::uint32_t i = 0; i <= max_ids; ++i)
        ids.push_back(device_filter(target) + "\\UNIT" + std::to_string(i));
    }
    if (scenario == "mixed-case") {
      auto id = target;
      for (auto &c : id)
        if (c >= 'A' && c <= 'Z')
          c = static_cast<char>(c - 'A' + 'a');
      ids.push_back(id);
    }
    std::size_t index = 0;
    for (const auto &id : ids) {
      for (const char c : id)
        result.multi_sz.at(index++) = static_cast<wchar_t>(c);
      result.multi_sz.at(index++) = 0;
    }
    result.multi_sz.at(index) = 0;
    if (scenario == "nonascii")
      result.multi_sz[0] = 0x8000;
    return result;
  }
};
} // namespace rocell::usb_presence
