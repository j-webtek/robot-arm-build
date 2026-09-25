#include "windows_api.h"
#include <windows.h>
#include <initguid.h>
#include <algorithm>
#include <cfgmgr32.h>
#include <cstring>
#include <devpkey.h>
#include <map>
#include <set>
#include <setupapi.h>
#include <stdexcept>
#include <usbioctl.h>
#include <usbiodef.h>
#include <winioctl.h>

namespace rocell::usb_identity {
static_assert(sizeof(USB_NODE_CONNECTION_INFORMATION_EX) == 35);
static_assert(sizeof(USB_PIPE_INFO) == 11);
static_assert(sizeof(USB_NODE_CONNECTION_INFORMATION_EX_V2) == 16);
static_assert(sizeof(USB_DEVICE_DESCRIPTOR) == 18);
namespace {
Result bad(const char *code = "API_FAILED", const char *domain = "CONTRACT",
           std::uint32_t n = 0) {
  Result r;
  r.error = {code, domain, n};
  return r;
}
Result win(DWORD n) { return bad("API_FAILED", "WIN32", n); }
Result cm(CONFIGRET n) { return bad("API_FAILED", "CM", n); }
std::wstring wide(const std::string &s) {
  if (s.empty() || s.size() > 4096)
    throw std::runtime_error("BYTE_LIMIT");
  int n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(),
                              static_cast<int>(s.size()), nullptr, 0);
  if (n <= 0)
    throw std::runtime_error("UTF16_INVALID");
  std::wstring out(static_cast<std::size_t>(n), L'\0');
  if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, s.data(),
                          static_cast<int>(s.size()), out.data(), n) != n)
    throw std::runtime_error("UTF16_INVALID");
  return out;
}
std::string narrow(const wchar_t *s, std::size_t n) {
  Bytes b(n * 2);
  if (n)
    std::memcpy(b.data(), s, n * 2);
  return utf16(b, false);
}
Result text_result(const wchar_t *data, std::size_t bytes) {
  if (bytes < 2 || bytes % 2 || bytes > 4096)
    return bad("BYTE_LIMIT");
  const auto chars = bytes / 2;
  const auto end = std::find(data, data + chars, L'\0');
  if (end == data + chars || end == data)
    return bad("UTF16_INVALID");
  if (std::any_of(end, data + chars, [](wchar_t c) { return c != 0; }))
    return bad("UTF16_INVALID");
  Result r;
  r.ok = true;
  r.text = narrow(data, static_cast<std::size_t>(end - data));
  r.returned = static_cast<std::uint32_t>(bytes);
  return r;
}
Result device_id(DEVINST node) {
  wchar_t buffer[MAX_DEVICE_ID_LEN]{};
  const auto status = CM_Get_Device_IDW(node, buffer, MAX_DEVICE_ID_LEN, 0);
  if (status != CR_SUCCESS)
    return cm(status);
  const auto length = wcsnlen_s(buffer, MAX_DEVICE_ID_LEN);
  return text_result(buffer, (length + 1) * 2);
}
Result interface_for(DEVINST node, const GUID &guid) {
  auto id = device_id(node);
  if (!id.ok)
    return id;
  auto instance = wide(id.text);
  ULONG size = 0;
  auto status = CM_Get_Device_Interface_List_SizeW(
      &size, const_cast<GUID *>(&guid), instance.data(),
      CM_GET_DEVICE_INTERFACE_LIST_PRESENT);
  if (status != CR_SUCCESS)
    return cm(status);
  if (size == 0 || size > 2048)
    return bad("BYTE_LIMIT");
  std::vector<wchar_t> data(size, L'\xffff');
  status = CM_Get_Device_Interface_ListW(const_cast<GUID *>(&guid),
                                         instance.data(), data.data(), size,
                                         CM_GET_DEVICE_INTERFACE_LIST_PRESENT);
  if (status != CR_SUCCESS)
    return cm(status);
  if (data.back() != L'\0')
    return bad("UTF16_INVALID");
  Result r;
  r.ok = true;
  r.returned = size * 2;
  if (data.front() == L'\0')
    return r;
  auto end = std::find(data.begin(), data.end(), L'\0');
  if (end == data.end() ||
      std::any_of(end, data.end(), [](wchar_t c) { return c != 0; }))
    return bad("ANCESTRY_AMBIGUOUS");
  r.text = narrow(data.data(), static_cast<std::size_t>(end - data.begin()));
  return r;
}
Result map_endpoint(const std::string &endpoint) {
  auto path = wide(endpoint);
  HDEVINFO info = SetupDiCreateDeviceInfoList(nullptr, nullptr);
  if (info == INVALID_HANDLE_VALUE)
    return win(GetLastError());
  Result r;
  try {
    SP_DEVICE_INTERFACE_DATA iface{};
    iface.cbSize = sizeof(iface);
    if (!SetupDiOpenDeviceInterfaceW(info, path.c_str(), 0, &iface))
      r = win(GetLastError());
    else {
      alignas(SP_DEVICE_INTERFACE_DETAIL_DATA_W) unsigned char bytes[4096]{};
      auto *detail =
          reinterpret_cast<SP_DEVICE_INTERFACE_DETAIL_DATA_W *>(bytes);
      detail->cbSize = sizeof(*detail);
      SP_DEVINFO_DATA dev{};
      dev.cbSize = sizeof(dev);
      DWORD actual = 0;
      if (!SetupDiGetDeviceInterfaceDetailW(info, &iface, detail, sizeof(bytes),
                                            &actual, &dev))
        r = win(GetLastError());
      else if (actual > sizeof(bytes) ||
               actual <
                   offsetof(SP_DEVICE_INTERFACE_DETAIL_DATA_W, DevicePath) + 2)
        r = bad("BYTE_LIMIT");
      else {
        r = text_result(
            detail->DevicePath,
            actual - offsetof(SP_DEVICE_INTERFACE_DETAIL_DATA_W, DevicePath));
        r.number = dev.DevInst;
      }
    }
  } catch (const std::exception &) {
    r = bad("UTF16_INVALID");
  }
  if (!SetupDiDestroyDeviceInfoList(info)) {
    r.ok = false;
    r.error = {"CLOSE_FAILED", "WIN32", GetLastError()};
  }
  return r;
}
} // namespace
struct WindowsUsbIdentityApi::State {
  std::map<std::uint32_t, HANDLE> handles;
  std::set<std::uint32_t> close_attempted;
};
WindowsUsbIdentityApi::WindowsUsbIdentityApi()
    : state(std::make_unique<State>()) {}
WindowsUsbIdentityApi::~WindowsUsbIdentityApi() =
    default; // OS exit owns unresolved closes; never retry an uncertain close.
Result WindowsUsbIdentityApi::call(const Input &i) {
  try {
    if (i.maximum > 4096)
      return bad("BYTE_LIMIT");
    if (i.op == Op::MapEndpoint)
      return map_endpoint(i.text);
    if (i.op == Op::DeviceId)
      return device_id(i.target);
    if (i.op == Op::Parent) {
      DEVINST parent = 0;
      auto code = CM_Get_Parent(&parent, i.target, 0);
      if (code != CR_SUCCESS)
        return cm(code);
      Result r;
      r.ok = true;
      r.number = parent;
      return r;
    }
    if (i.op == Op::HubInterface)
      return interface_for(i.target, GUID_DEVINTERFACE_USB_HUB);
    if (i.op == Op::HostController)
      return interface_for(i.target, GUID_DEVINTERFACE_USB_HOST_CONTROLLER);
    if (i.op == Op::DriverKey) {
      wchar_t buffer[2048]{};
      ULONG bytes = sizeof(buffer);
      DEVPROPTYPE type = 0;
      auto code =
          CM_Get_DevNode_PropertyW(i.target, &DEVPKEY_Device_Driver, &type,
                                   reinterpret_cast<BYTE *>(buffer), &bytes, 0);
      if (code != CR_SUCCESS)
        return cm(code);
      if (type != DEVPROP_TYPE_STRING)
        return bad("PROPERTY_TYPE");
      return text_result(buffer, bytes);
    }
    if (i.op == Op::OpenHub) {
      if (i.handle == 0 || !state->handles.empty())
        return bad("REQUEST_INVALID");
      auto path = wide(i.text);
      // Reserve ownership bookkeeping before acquiring a kernel handle.
      auto slot = state->handles.emplace(i.handle, INVALID_HANDLE_VALUE).first;
      // Query-only operations may need GENERIC_WRITE access to the hub
      // interface; this is a real device handle, never labeled as OS-only
      // metadata.
      auto h = CreateFileW(path.c_str(), GENERIC_WRITE,
                           FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr,
                           OPEN_EXISTING, 0, nullptr);
      if (h == INVALID_HANDLE_VALUE) {
        const auto error = GetLastError();
        state->handles.erase(slot);
        return win(error);
      }
      slot->second = h;
      Result r;
      r.ok = true;
      return r;
    }
    auto found = state->handles.find(i.handle);
    if (found == state->handles.end())
      return bad("REQUEST_INVALID");
    if (i.op == Op::CloseHub) {
      if (!state->close_attempted.insert(i.handle).second)
        return bad("CLOSE_FAILED");
      if (!CloseHandle(found->second))
        return win(GetLastError());
      state->handles.erase(found);
      Result r;
      r.ok = true;
      return r;
    }
    DWORD ioctl = 0;
    Bytes data(i.maximum, 0);
    DWORD returned = 0;
    if (i.op == Op::HubInformation) {
      if (data.size() < sizeof(USB_NODE_INFORMATION))
        return bad("BYTE_LIMIT");
      ioctl = IOCTL_USB_GET_NODE_INFORMATION;
    } else if (i.op == Op::ConnectionDriverKey) {
      if (data.size() < sizeof(USB_NODE_CONNECTION_DRIVERKEY_NAME))
        return bad("BYTE_LIMIT");
      ioctl = IOCTL_USB_GET_NODE_CONNECTION_DRIVERKEY_NAME;
    } else if (i.op == Op::ConnectionEx) {
      if (data.size() < 35)
        return bad("BYTE_LIMIT");
      ioctl = IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX;
    } else if (i.op == Op::ConnectionExV2) {
      if (data.size() != 16)
        return bad("BYTE_LIMIT");
      ioctl = IOCTL_USB_GET_NODE_CONNECTION_INFORMATION_EX_V2;
      data[4] = 16;
      data[8] = 7;
    } else if (i.op >= Op::DeviceDescriptor && i.op <= Op::SerialDescriptor) {
      if (i.maximum < sizeof(USB_DESCRIPTOR_REQUEST))
        return bad("BYTE_LIMIT");
      // Trace lengths are the actual IOCTL buffers, including the 12-byte
      // header.
      auto *request = reinterpret_cast<USB_DESCRIPTOR_REQUEST *>(data.data());
      request->ConnectionIndex = i.port;
      request->SetupPacket.wValue = static_cast<USHORT>(
          (i.op == Op::DeviceDescriptor ? USB_DEVICE_DESCRIPTOR_TYPE
                                        : USB_STRING_DESCRIPTOR_TYPE)
          << 8);
      if (i.op == Op::SerialDescriptor)
        request->SetupPacket.wValue |= i.index;
      request->SetupPacket.wIndex = i.language;
      request->SetupPacket.wLength =
          static_cast<USHORT>(i.maximum - sizeof(USB_DESCRIPTOR_REQUEST));
      ioctl = IOCTL_USB_GET_DESCRIPTOR_FROM_NODE_CONNECTION;
    } else
      return bad("REQUEST_INVALID");
    if (i.op != Op::HubInformation && i.op < Op::DeviceDescriptor)
      std::memcpy(data.data(), &i.port, sizeof(i.port));
    // Synchronous call is contained by the parent-owned process deadline. Child
    // boundary checks cannot promise that a stuck kernel call was cancelled.
    if (!DeviceIoControl(found->second, ioctl, data.data(),
                         static_cast<DWORD>(data.size()), data.data(),
                         static_cast<DWORD>(data.size()), &returned, nullptr))
      return win(GetLastError());
    if (returned > data.size())
      return bad("BYTE_LIMIT");
    data.resize(returned);
    Result r;
    r.ok = true;
    r.returned = static_cast<std::uint32_t>(data.size());
    if (i.op >= Op::DeviceDescriptor) {
      if (data.size() < sizeof(USB_DESCRIPTOR_REQUEST))
        return bad("DESCRIPTOR_MALFORMED");
      data.erase(data.begin(), data.begin() + sizeof(USB_DESCRIPTOR_REQUEST));
    }
    if (i.op == Op::HubInformation) {
      if (data.size() < sizeof(USB_NODE_INFORMATION))
        return bad("DESCRIPTOR_MALFORMED");
      auto *n = reinterpret_cast<USB_NODE_INFORMATION *>(data.data());
      r.number = n->u.HubInformation.HubDescriptor.bNumberOfPorts;
    } else if (i.op == Op::ConnectionDriverKey) {
      if (data.size() <
          offsetof(USB_NODE_CONNECTION_DRIVERKEY_NAME, DriverKeyName) + 2)
        return bad("DESCRIPTOR_MALFORMED");
      auto *key =
          reinterpret_cast<USB_NODE_CONNECTION_DRIVERKEY_NAME *>(data.data());
      if (key->ActualLength > data.size() || key->ConnectionIndex != i.port)
        return bad("PORT_MISMATCH");
      auto decoded = text_result(
          key->DriverKeyName,
          key->ActualLength -
              offsetof(USB_NODE_CONNECTION_DRIVERKEY_NAME, DriverKeyName));
      if (!decoded.ok)
        return decoded;
      r.text = decoded.text;
    } else
      r.bytes = std::move(data);
    return r;
  } catch (const std::exception &e) {
    const std::string code = e.what();
    return bad(code == "UTF16_INVALID" ? "UTF16_INVALID"
               : code == "BYTE_LIMIT"  ? "BYTE_LIMIT"
                                       : "API_FAILED");
  }
}
} // namespace rocell::usb_identity
