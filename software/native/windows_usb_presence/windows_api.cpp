#include "windows_api.h"
#include <windows.h>
#include <cfgmgr32.h>
#include <stdexcept>

namespace rocell::usb_presence {
namespace {
constexpr ULONG flags =
    CM_GETIDLIST_FILTER_ENUMERATOR | CM_GETIDLIST_FILTER_PRESENT;
std::wstring fixed_filter(const std::string &filter) {
  // Validation cannot accept a full instance, interface, root or caller flag.
  if (device_filter(filter + "\\VALIDATION") != filter)
    throw std::runtime_error("FILTER_REQUIRED");
  return std::wstring(filter.begin(), filter.end());
}
} // namespace
ApiResult WindowsPresenceApi::size(const std::string &filter) {
  const auto native = fixed_filter(filter);
  ULONG count = 0;
  ApiResult out;
  out.code = CM_Get_Device_ID_List_SizeW(&count, native.c_str(), flags);
  out.required_chars = count;
  return out;
}
ApiResult WindowsPresenceApi::list(const std::string &filter,
                                   std::uint32_t capacity) {
  if (capacity == 0 || capacity > max_chars)
    throw std::runtime_error("LIST_SIZE_LIMIT");
  const auto native = fixed_filter(filter);
  ApiResult out;
  // Nonzero padding makes a missing terminator detectable; capacity may exceed
  // the actual list length, which the parser derives from MULTI_SZ termination.
  out.multi_sz.assign(capacity, static_cast<wchar_t>(0xffff));
  out.code = CM_Get_Device_ID_ListW(native.c_str(), out.multi_sz.data(),
                                    capacity, flags);
  return out;
}
} // namespace rocell::usb_presence
