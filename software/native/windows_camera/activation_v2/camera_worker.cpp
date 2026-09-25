// One explicit, finite Media Foundation campaign per process. No retries,
// numerical device selection, motion surface, SDK DLL loading, or shell calls.
// The Python coordinator boundary must consume exact authority BEFORE launch.
// This executable is not itself an authorization issuer or a hardware release.
#include <windows.h>
#include <mfapi.h>
#include <mfidl.h>
#include <mfreadwrite.h>
#include <mferror.h>
#include <strmif.h>
#include <wrl/client.h>
#include <algorithm>
#include <atomic>
#include <cstdint>
#include <filesystem>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>
#include "identity_metadata.h"
#include "camera_activation_entry.h"
#include "camera_activation_launch.h"
#include "camera_cleanup.h"
#ifdef ROCELL_ENABLE_OWNED_CAPTURE
#include "capture_admission_protocol.h"
#endif

using Microsoft::WRL::ComPtr;
namespace fs = std::filesystem;

namespace {
constexpr uint64_t kMaxFrame = 64ULL * 1024 * 1024;
constexpr uint64_t kMaxTotal = 2ULL * 1024 * 1024 * 1024;
constexpr unsigned kMaxFrames = 32;
constexpr DWORD kFirstVideoStream = static_cast<DWORD>(MF_SOURCE_READER_FIRST_VIDEO_STREAM);
constexpr DWORD kAllStreams = static_cast<DWORD>(MF_SOURCE_READER_ALL_STREAMS);
constexpr char kSchema[] = "rocell.windows_camera.v1";

struct Failure : std::runtime_error {
  explicit Failure(const char* reason) : std::runtime_error(reason) {}
};
void require(bool condition, const char* reason) {
  if (!condition) throw Failure(reason);
}
void hrcheck(HRESULT result, const char* reason) {
  if (FAILED(result)) throw Failure(reason);
}
std::string utf8(const std::wstring& value) {
  require(value.size() <= 4096, "TEXT_LIMIT");
  if (value.empty()) return {};
  const int size = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
      static_cast<int>(value.size()), nullptr, 0, nullptr, nullptr);
  require(size > 0, "INVALID_UNICODE");
  std::string out(static_cast<size_t>(size), '\0');
  require(WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, value.data(),
      static_cast<int>(value.size()), out.data(), size, nullptr, nullptr) == size,
      "INVALID_UNICODE");
  return out;
}
std::string quote(const std::string& value) {
  std::ostringstream out;
  out << '"';
  static constexpr char hex[] = "0123456789abcdef";
  for (unsigned char c : value) {
    if (c == '"' || c == '\\') out << '\\' << static_cast<char>(c);
    else if (c < 32) out << "\\u00" << hex[c >> 4] << hex[c & 15];
    else out << static_cast<char>(c);
  }
  out << '"';
  return out.str();
}
std::string quote(const std::wstring& value) { return quote(utf8(value)); }
template <class T> std::string nullable(const std::optional<T>& value) {
  return value ? std::to_string(*value) : "null";
}
std::wstring attr_string(IMFAttributes* attributes, REFGUID name) {
  UINT32 size = 0;
  hrcheck(attributes->GetStringLength(name, &size), "DEVICE_ATTRIBUTE_UNAVAILABLE");
  require(size > 0 && size <= 4096, "DEVICE_ATTRIBUTE_SIZE");
  std::vector<wchar_t> text(static_cast<size_t>(size) + 1);
  hrcheck(attributes->GetString(name, text.data(), size + 1, nullptr), "DEVICE_ATTRIBUTE_UNAVAILABLE");
  return std::wstring(text.data(), size);
}
struct Mode {
  UINT32 width = 0, height = 0, fps_n = 0, fps_d = 0;
  GUID guid = GUID_NULL;
  std::string subtype;
  std::optional<LONG> stride;
  bool matches(const Mode& other) const {
    return width == other.width && height == other.height && guid == other.guid &&
      uint64_t(fps_n) * other.fps_d == uint64_t(other.fps_n) * fps_d;
  }
  std::string json() const {
    std::ostringstream out;
    out << "{\"width\":" << width << ",\"height\":" << height
        << ",\"fps_numerator\":" << fps_n << ",\"fps_denominator\":" << fps_d
        << ",\"subtype\":" << quote(subtype) << ",\"stride_bytes\":" << nullable(stride) << '}';
    return out.str();
  }
};
Mode read_mode(IMFMediaType* type) {
  Mode mode;
  hrcheck(MFGetAttributeSize(type, MF_MT_FRAME_SIZE, &mode.width, &mode.height), "MODE_SIZE_UNAVAILABLE");
  hrcheck(MFGetAttributeRatio(type, MF_MT_FRAME_RATE, &mode.fps_n, &mode.fps_d), "MODE_RATE_UNAVAILABLE");
  hrcheck(type->GetGUID(MF_MT_SUBTYPE, &mode.guid), "MODE_SUBTYPE_UNAVAILABLE");
  require(mode.width > 0 && mode.width <= 16384 && mode.height > 0 && mode.height <= 16384 &&
      mode.fps_n > 0 && mode.fps_n <= 1000000 && mode.fps_d > 0 && mode.fps_d <= 1000000,
      "MODE_OUTSIDE_BOUNDS");
  if (mode.guid == MFVideoFormat_YUY2) mode.subtype = "YUY2";
  else {
    wchar_t guid[40]{};
    require(StringFromGUID2(mode.guid, guid, 40) > 0, "MODE_SUBTYPE_UNAVAILABLE");
    mode.subtype = utf8(guid);
  }
  UINT32 stride = 0;
  if (SUCCEEDED(type->GetUINT32(MF_MT_DEFAULT_STRIDE, &stride))) mode.stride = static_cast<LONG>(stride);
  return mode;
}

struct Device {
  ComPtr<IMFActivate> activate;
  std::wstring endpoint, friendly;
  std::string json() const {
    return "{\"symbolic_link\":" + quote(endpoint) + ",\"friendly_name\":" + quote(friendly) + '}';
  }
};
std::vector<Device> enumerate_metadata() {
  ComPtr<IMFAttributes> attributes;
  hrcheck(MFCreateAttributes(&attributes, 1), "MF_ATTRIBUTES_FAILED");
  hrcheck(attributes->SetGUID(MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE,
      MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_GUID), "MF_ATTRIBUTES_FAILED");
  IMFActivate** raw = nullptr;
  UINT32 count = 0;
  hrcheck(MFEnumDeviceSources(attributes.Get(), &raw, &count), "MF_INVENTORY_FAILED");
  // Attach every COM reference before inspecting attributes, so exceptions
  // cannot leak the remaining activation objects. Enumeration does not open.
  std::vector<ComPtr<IMFActivate>> owners;
  for (UINT32 i = 0; i < count; ++i) {
    ComPtr<IMFActivate> owner;
    owner.Attach(raw[i]);
    owners.push_back(std::move(owner));
  }
  CoTaskMemFree(raw);
  require(count <= 64, "DEVICE_COUNT_LIMIT");
  std::set<std::wstring> seen;
  std::vector<Device> devices;
  for (const auto& owner : owners) {
    Device device;
    device.activate = owner;
    device.endpoint = attr_string(owner.Get(), MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK);
    device.friendly = attr_string(owner.Get(), MF_DEVSOURCE_ATTRIBUTE_FRIENDLY_NAME);
    require(seen.insert(device.endpoint).second, "AMBIGUOUS_ENDPOINT");
    devices.push_back(std::move(device));
  }
  return devices;
}

struct Setting { std::string id; LONG value; LONG flags; };
struct Control {
  std::string id;
  LONG property = 0, minimum = 0, maximum = 0, step = 0, default_value = 0;
  LONG caps = 0, value = 0, flags = 0;
  bool camera = false;
  std::string unit;
  std::string json() const {
    std::ostringstream out;
    out << "{\"control_id\":" << quote(id) << ",\"minimum\":" << minimum
        << ",\"maximum\":" << maximum << ",\"step\":" << step
        << ",\"default\":" << default_value << ",\"capability_flags\":" << caps
        << ",\"value\":" << value << ",\"flags\":" << flags << ",\"unit\":" << quote(unit) << '}';
    return out.str();
  }
};
std::vector<Control> controls_for(IMFMediaSource* source) {
  ComPtr<IAMVideoProcAmp> video;
  ComPtr<IAMCameraControl> camera;
  source->QueryInterface(IID_PPV_ARGS(&video));
  source->QueryInterface(IID_PPV_ARGS(&camera));
  const struct { const char* id; LONG property; bool camera; const char* unit; } definitions[] = {
    {"brightness", VideoProcAmp_Brightness, false, "driver_units"},
    {"contrast", VideoProcAmp_Contrast, false, "driver_units"},
    {"saturation", VideoProcAmp_Saturation, false, "driver_units"},
    {"white_balance", VideoProcAmp_WhiteBalance, false, "kelvin"},
    {"gain", VideoProcAmp_Gain, false, "driver_units"},
    {"exposure", CameraControl_Exposure, true, "log2_seconds"},
  };
  std::vector<Control> result;
  for (const auto& definition : definitions) {
    Control c;
    c.id = definition.id; c.property = definition.property;
    c.camera = definition.camera; c.unit = definition.unit;
    HRESULT range = E_NOINTERFACE, current = E_NOINTERFACE;
    if (c.camera && camera) {
      range = camera->GetRange(c.property, &c.minimum, &c.maximum, &c.step, &c.default_value, &c.caps);
      current = camera->Get(c.property, &c.value, &c.flags);
    } else if (!c.camera && video) {
      range = video->GetRange(c.property, &c.minimum, &c.maximum, &c.step, &c.default_value, &c.caps);
      current = video->Get(c.property, &c.value, &c.flags);
    }
    // No synthetic range or software autofocus: unsupported readback is absent.
    if (SUCCEEDED(range) && SUCCEEDED(current) && c.step > 0) result.push_back(c);
  }
  return result;
}
void apply_controls(IMFMediaSource* source, const std::vector<Setting>& requested,
                    std::vector<Control>& observed, unsigned& attempts) {
  // Validate the entire immutable settings batch before the first control write.
  for (const auto& setting : requested) {
    const auto found = std::find_if(observed.begin(), observed.end(),
        [&](const Control& c) { return c.id == setting.id; });
    require(found != observed.end(), "CONTROL_UNSUPPORTED");
    require(setting.value >= found->minimum && setting.value <= found->maximum &&
      (int64_t(setting.value) - found->minimum) % found->step == 0 &&
      (found->caps & setting.flags) == setting.flags, "CONTROL_VALUE_UNSUPPORTED");
  }
  ComPtr<IAMVideoProcAmp> video;
  ComPtr<IAMCameraControl> camera;
  source->QueryInterface(IID_PPV_ARGS(&video));
  source->QueryInterface(IID_PPV_ARGS(&camera));
  for (const auto& setting : requested) {
    auto& c = *std::find_if(observed.begin(), observed.end(),
        [&](const Control& x) { return x.id == setting.id; });
    ++attempts;
    HRESULT result = E_NOINTERFACE;
    if (c.camera && camera) result = camera->Set(c.property, setting.value, setting.flags);
    else if (!c.camera && video) result = video->Set(c.property, setting.value, setting.flags);
    hrcheck(result, "CONTROL_SET_FAILED");
    if (c.camera && camera) result = camera->Get(c.property, &c.value, &c.flags);
    else if (!c.camera && video) result = video->Get(c.property, &c.value, &c.flags);
    hrcheck(result, "CONTROL_READBACK_FAILED");
    require(c.flags == setting.flags && (setting.flags != 2 || c.value == setting.value),
        "CONTROL_READBACK_MISMATCH");
  }
}

struct Frame {
  std::string filename;
  uint64_t length = 0, row0 = 0;
  LONG stride = 0;
  unsigned sequence = 0;
  LONGLONG timestamp = 0, arrival = 0, frequency = 0;
  std::optional<bool> discontinuity;
  std::string json() const {
    std::ostringstream out;
    out << "{\"filename\":" << quote(filename) << ",\"length_bytes\":" << length
        << ",\"stride_bytes\":" << stride << ",\"row0_offset_bytes\":" << row0
        << ",\"host_sequence\":" << sequence << ",\"media_timestamp_100ns\":" << timestamp
        << ",\"host_arrival_qpc\":" << arrival << ",\"qpc_frequency\":" << frequency
        << ",\"discontinuity\":" << (discontinuity ? (*discontinuity ? "true" : "false") : "null") << '}';
    return out.str();
  }
};

class Callback final : public IMFSourceReaderCallback {
  std::atomic<ULONG> references_{1};
public:
  HANDLE ready = CreateEventW(nullptr, TRUE, FALSE, nullptr);
  std::mutex mutex;
  ComPtr<IMFSample> sample;
  HRESULT status = S_OK;
  DWORD flags = 0;
  LONGLONG timestamp = 0, arrival = 0;
  Callback() { require(ready != nullptr, "CALLBACK_EVENT_FAILED"); }
  ~Callback() { CloseHandle(ready); }
  STDMETHODIMP QueryInterface(REFIID iid, void** object) override {
    if (!object) return E_POINTER;
    *object = nullptr;
    if (iid == __uuidof(IUnknown) || iid == __uuidof(IMFSourceReaderCallback)) {
      *object = static_cast<IMFSourceReaderCallback*>(this); AddRef(); return S_OK;
    }
    return E_NOINTERFACE;
  }
  STDMETHODIMP_(ULONG) AddRef() override { return ++references_; }
  STDMETHODIMP_(ULONG) Release() override {
    const ULONG count = --references_; if (count == 0) delete this; return count;
  }
  STDMETHODIMP OnReadSample(HRESULT hr, DWORD, DWORD stream_flags,
                            LONGLONG media_time, IMFSample* received) override {
    std::lock_guard<std::mutex> lock(mutex);
    LARGE_INTEGER qpc{}; QueryPerformanceCounter(&qpc);
    status = hr; flags = stream_flags; timestamp = media_time; arrival = qpc.QuadPart;
    sample = received;
    SetEvent(ready);
    return S_OK;
  }
  STDMETHODIMP OnEvent(DWORD, IMFMediaEvent*) override { return S_OK; }
  STDMETHODIMP OnFlush(DWORD) override { return S_OK; }
  void prepare() {
    std::lock_guard<std::mutex> lock(mutex);
    sample.Reset(); ResetEvent(ready);
  }
};

struct Options {
  std::string operation;
  std::wstring endpoint;
  fs::path output;
  uint64_t max_ms = 5000, max_frame = kMaxFrame, max_total = kMaxTotal;
  unsigned frames = 1;
  std::optional<Mode> mode;
  std::vector<Setting> settings;
};
uint64_t number(const std::wstring& text, uint64_t low, uint64_t high) {
  require(!text.empty() && text.size() <= 12 &&
      std::all_of(text.begin(), text.end(), [](wchar_t c) { return c >= L'0' && c <= L'9'; }),
      "INVALID_NUMERIC_ARGUMENT");
  const uint64_t value = std::stoull(text);
  require(value >= low && value <= high, "ARGUMENT_OUTSIDE_BUDGET");
  return value;
}
std::vector<Setting> parse_settings(const std::wstring& text) {
  const std::set<std::string> allowed{"exposure", "gain", "white_balance", "brightness", "contrast", "saturation"};
  std::set<std::string> seen;
  std::vector<Setting> result;
  std::istringstream stream(utf8(text));
  std::string part;
  while (std::getline(stream, part, ';')) {
    const size_t a = part.find(','), b = part.find(',', a == std::string::npos ? 0 : a + 1);
    require(a != std::string::npos && b != std::string::npos && part.find(',', b + 1) == std::string::npos, "INVALID_CONTROL_ARGUMENT");
    Setting setting; setting.id = part.substr(0, a);
    require(allowed.count(setting.id) == 1 && seen.insert(setting.id).second, "INVALID_CONTROL_ARGUMENT");
    const auto value = part.substr(a + 1, b - a - 1);
    require(!value.empty() && value.size() <= 12, "INVALID_CONTROL_ARGUMENT");
    size_t used = 0; const auto parsed = std::stoll(value, &used);
    require(used == value.size() && parsed >= LONG_MIN && parsed <= LONG_MAX, "INVALID_CONTROL_ARGUMENT");
    setting.value = static_cast<LONG>(parsed);
    const auto mode = part.substr(b + 1);
    require(mode == "auto" || mode == "manual", "INVALID_CONTROL_ARGUMENT");
    setting.flags = mode == "auto" ? 1 : 2;
    result.push_back(setting);
  }
  require(!result.empty() && result.size() <= 6, "INVALID_CONTROL_ARGUMENT");
  return result;
}
Options parse_options(const std::vector<std::wstring>& arguments) {
  require(arguments.size() >= 1, "MISSING_OPERATION");
  Options o; o.operation = utf8(arguments[0]);
  require(o.operation == "inventory" || o.operation == "probe" || o.operation == "capture", "UNKNOWN_OPERATION");
  std::map<std::wstring, std::wstring> values;
  for (size_t i = 1; i < arguments.size(); i += 2) {
    require(i + 1 < arguments.size() && values.emplace(arguments[i], arguments[i + 1]).second, "INVALID_ARGUMENTS");
  }
  std::set<std::wstring> required{L"--max-ms"};
  if (o.operation != "inventory") required.insert(L"--endpoint");
  if (o.operation == "capture") {
    for (const auto* name : {L"--width", L"--height", L"--fps-n", L"--fps-d", L"--frames", L"--frame-bytes", L"--total-bytes", L"--output"}) required.insert(name);
  }
  for (const auto& name : required) require(values.count(name) == 1, "MISSING_ARGUMENT");
  for (const auto& item : values) require(required.count(item.first) == 1 ||
      (o.operation == "capture" && item.first == L"--controls"), "UNKNOWN_ARGUMENT");
  o.max_ms = number(values.at(L"--max-ms"), 100, o.operation == "inventory" ? 30000 : 300000);
  if (o.operation != "inventory") {
    o.endpoint = values.at(L"--endpoint");
    require(!o.endpoint.empty() && utf8(o.endpoint).size() <= 4096, "INVALID_ENDPOINT");
  }
  if (o.operation == "capture") {
    Mode m;
    m.width = static_cast<UINT32>(number(values.at(L"--width"), 2, 16384));
    m.height = static_cast<UINT32>(number(values.at(L"--height"), 1, 16384));
    m.fps_n = static_cast<UINT32>(number(values.at(L"--fps-n"), 1, 1000000));
    m.fps_d = static_cast<UINT32>(number(values.at(L"--fps-d"), 1, 1000000));
    m.guid = MFVideoFormat_YUY2; m.subtype = "YUY2"; o.mode = m;
    o.frames = static_cast<unsigned>(number(values.at(L"--frames"), 1, kMaxFrames));
    o.max_frame = number(values.at(L"--frame-bytes"), 1, kMaxFrame);
    o.max_total = number(values.at(L"--total-bytes"), o.max_frame, kMaxTotal);
    require(m.width % 2 == 0 && uint64_t(m.width) * m.height * 2 <= o.max_frame, "REQUESTED_FRAME_TOO_LARGE");
    o.output = values.at(L"--output");
    require(o.output.is_absolute(), "OUTPUT_NOT_ABSOLUTE");
    if (values.count(L"--controls")) o.settings = parse_settings(values.at(L"--controls"));
  }
  return o;
}
void validate_output(const fs::path& path) {
  require(fs::is_directory(path) && fs::is_empty(path), "OUTPUT_NOT_EMPTY_DIRECTORY");
  auto current = path;
  while (!current.empty()) {
    const DWORD attributes = GetFileAttributesW(current.c_str());
    require(attributes != INVALID_FILE_ATTRIBUTES && !(attributes & FILE_ATTRIBUTE_REPARSE_POINT), "OUTPUT_REPARSE_POINT");
    if (current == current.parent_path()) break;
    current = current.parent_path();
  }
}
bool rows_fit(uint64_t length, int64_t row0, LONG stride, UINT32 width, UINT32 height) {
  const int64_t last = row0 + int64_t(stride) * (height - 1);
  return std::abs(int64_t(stride)) >= int64_t(width) * 2 &&
      std::min(row0, last) >= 0 && uint64_t(std::max(row0, last)) + uint64_t(width) * 2 <= length;
}
Frame write_frame(IMFSample* sample, const Mode& mode, const Options& options,
                  unsigned sequence, LONGLONG timestamp, LONGLONG arrival, uint64_t& total) {
  Frame frame;
  frame.sequence = sequence; frame.timestamp = timestamp; frame.arrival = arrival;
  LARGE_INTEGER frequency{};
  require(QueryPerformanceFrequency(&frequency) && frequency.QuadPart > 0, "HOST_CLOCK_UNAVAILABLE");
  frame.frequency = frequency.QuadPart;
  UINT32 discontinuity = 0;
  if (SUCCEEDED(sample->GetUINT32(MFSampleExtension_Discontinuity, &discontinuity))) frame.discontinuity = discontinuity != 0;
  DWORD count = 0;
  hrcheck(sample->GetBufferCount(&count), "SAMPLE_BUFFER_UNAVAILABLE");
  require(count == 1, "MULTIPLANE_SAMPLE_UNSUPPORTED");
  ComPtr<IMFMediaBuffer> buffer;
  hrcheck(sample->GetBufferByIndex(0, &buffer), "SAMPLE_BUFFER_UNAVAILABLE");
  DWORD current_length = 0;
  hrcheck(buffer->GetCurrentLength(&current_length), "SAMPLE_LENGTH_UNAVAILABLE");
  ComPtr<IMF2DBuffer2> two;
  buffer.As(&two);
  BYTE *start = nullptr, *row0 = nullptr;
  DWORD length = 0;
  bool locked = false;
  HANDLE file = INVALID_HANDLE_VALUE;
  try {
    if (two) {
      hrcheck(two->Lock2DSize(MF2DBuffer_LockFlags_Read, &row0, &frame.stride, &start, &length), "SAMPLE_LOCK_FAILED");
      locked = true;
      // Do not write spare allocation capacity as if it were sample data.
      // A different 2D layout needs an explicitly qualified repacking format.
      require(length == current_length, "BUFFER_LAYOUT_LENGTH_UNVERIFIED");
    } else {
      require(mode.stride.has_value(), "SAMPLE_STRIDE_UNAVAILABLE");
      DWORD capacity = 0;
      hrcheck(buffer->Lock(&start, &capacity, &length), "SAMPLE_LOCK_FAILED");
      locked = true;
      require(length <= capacity, "SAMPLE_LENGTH_INVALID");
      frame.stride = *mode.stride;
      // Native YUY2 is top-down. Without IMF2DBuffer2 there is no row-origin
      // observation that justifies guessing a negative-stride starting offset.
      require(frame.stride > 0, "NEGATIVE_STRIDE_REQUIRES_2D_BUFFER");
      row0 = start;
    }
    require(start && row0 && length <= options.max_frame &&
      reinterpret_cast<uintptr_t>(row0) >= reinterpret_cast<uintptr_t>(start), "SAMPLE_LENGTH_INVALID");
    frame.length = length;
    frame.row0 = reinterpret_cast<uintptr_t>(row0) - reinterpret_cast<uintptr_t>(start);
    require(frame.row0 <= length && rows_fit(length, static_cast<int64_t>(frame.row0), frame.stride, mode.width, mode.height), "SAMPLE_STRIDE_INVALID");
#ifdef ROCELL_ENABLE_OWNED_CAPTURE
    require(!options.mode->stride || frame.stride == *options.mode->stride, "REQUESTED_SAMPLE_STRIDE_MISMATCH");
#endif
    require(total + length <= options.max_total, "TOTAL_BYTES_LIMIT");
    std::ostringstream name;
    name << "frame-"; name.width(6); name.fill('0'); name << sequence << ".yuy2";
    frame.filename = name.str();
    const fs::path destination = options.output / frame.filename;
    // CREATE_NEW protects existing outputs; no cleanup path deletes material.
    file = CreateFileW(destination.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW,
        FILE_ATTRIBUTE_NORMAL | FILE_FLAG_OPEN_REPARSE_POINT, nullptr);
    require(file != INVALID_HANDLE_VALUE, "FRAME_CREATE_FAILED");
    DWORD written = 0;
    require(WriteFile(file, start, length, &written, nullptr) && written == length, "FRAME_WRITE_FAILED");
    require(FlushFileBuffers(file) != FALSE, "FRAME_FLUSH_FAILED");
    require(CloseHandle(file) != FALSE, "FRAME_CLOSE_FAILED");
    file = INVALID_HANDLE_VALUE;
    const HRESULT unlock = two ? two->Unlock2D() : buffer->Unlock();
    locked = false;
    hrcheck(unlock, "SAMPLE_UNLOCK_FAILED");
    total += length;
    return frame;
  } catch (...) {
    if (file != INVALID_HANDLE_VALUE) CloseHandle(file);
    if (locked) { if (two) two->Unlock2D(); else buffer->Unlock(); }
    throw;
  }
}

struct Receipt {
  Options options;
  std::string reason;
  std::vector<Device> devices;
  std::vector<Mode> modes;
  std::optional<Mode> observed;
  std::vector<Control> controls;
  std::vector<Frame> frames;
  unsigned activation_attempts = 0, opened = 0, control_attempts = 0, received = 0, shutdown_attempts = 0;
  std::optional<LONG> shutdown_hr, mf_shutdown_hr;
  bool source_released = true, com_uninitialized = false;
  std::string json() const {
    std::ostringstream out;
    out << "{\"schema\":" << quote(kSchema) << ",\"operation\":" << quote(options.operation)
        << ",\"status\":" << quote(reason.empty() ? "OK" : "FAILED")
        << ",\"reason_code\":" << (reason.empty() ? "null" : quote(reason))
        << ",\"selected_endpoint\":" << (options.endpoint.empty() ? "null" : quote(options.endpoint));
    out << ",\"devices\":[";
    for (size_t i = 0; i < devices.size(); ++i) { if (i) out << ','; out << devices[i].json(); }
    out << "],\"modes\":[";
    for (size_t i = 0; i < modes.size(); ++i) { if (i) out << ','; out << modes[i].json(); }
    out << "],\"requested_mode\":" << (options.mode ? options.mode->json() : "null")
        << ",\"observed_mode\":" << (observed ? observed->json() : "null") << ",\"controls\":[";
    for (size_t i = 0; i < controls.size(); ++i) { if (i) out << ','; out << controls[i].json(); }
    out << "],\"frames\":[";
    for (size_t i = 0; i < frames.size(); ++i) { if (i) out << ','; out << frames[i].json(); }
    out << "],\"counts\":{\"source_activation_attempts\":" << activation_attempts
        << ",\"source_opened\":" << opened << ",\"control_set_attempts\":" << control_attempts
        << ",\"samples_received\":" << received << ",\"frames_written\":" << frames.size()
        << ",\"source_shutdown_attempts\":" << shutdown_attempts << '}'
        << ",\"cleanup\":{\"source_shutdown_hr\":" << nullable(shutdown_hr)
        << ",\"source_released\":" << (source_released ? "true" : "false")
        << ",\"mf_shutdown_hr\":" << nullable(mf_shutdown_hr)
        << ",\"com_uninitialized\":" << (com_uninitialized ? "true" : "false") << '}'
        << ",\"limitations\":[\"UNIT_IDENTITY_REQUIRES_REVIEWED_OS_BINDING\","
           "\"USB_SPEED_AND_TOPOLOGY_NOT_OBSERVED\",\"SENSOR_SEQUENCE_UNAVAILABLE\","
           "\"MEDIA_TIMESTAMP_IS_NOT_EXPOSURE_TIME\",\"HOST_QPC_IS_ARRIVAL_ONLY\","
           "\"CONTROL_API_REQUIRES_RECEIVED_DRIVER_QUALIFICATION\",\"FOCUS_AND_APERTURE_ARE_MANUAL\"]}";
    return out.str();
  }
};

// The production adapter has no choices or policy of its own: it maps the
// shared, independently tested sequence onto this invocation's owned refs.
class NativeCleanupApi final : public rocell::camera_cleanup::Api {
  Receipt& receipt_;
  ComPtr<IMFActivate>& selected_;
  ComPtr<IMFMediaSource>& source_;
  ComPtr<IMFSourceReader>& reader_;
  ComPtr<Callback>& callback_;
 public:
  NativeCleanupApi(Receipt& receipt, ComPtr<IMFActivate>& selected,
                  ComPtr<IMFMediaSource>& source, ComPtr<IMFSourceReader>& reader,
                  ComPtr<Callback>& callback)
      : receipt_(receipt), selected_(selected), source_(source),
        reader_(reader), callback_(callback) {}
  std::int32_t shutdown_activation() override {
    return static_cast<std::int32_t>(selected_->ShutdownObject());
  }
  void release_reader() override { reader_.Reset(); }
  void release_callback() override { callback_.Reset(); }
  void release_source() override { source_.Reset(); }
  void release_activation() override { selected_.Reset(); }
  void release_enumerated_activations() override {
    for (auto& device : receipt_.devices) device.activate.Reset();
  }
  std::int32_t shutdown_media_foundation() override {
    return static_cast<std::int32_t>(MFShutdown());
  }
  void uninitialize_com() override { CoUninitialize(); }
};

void campaign(Receipt& receipt, ComPtr<IMFActivate>& selected,
              ComPtr<IMFMediaSource>& source, ComPtr<IMFSourceReader>& reader,
              ComPtr<Callback>& callback,
              const std::optional<rocell::activation_entry::Admitted>& admission,
              rocell::activation_gate::Gate& identity_gate) {
  const auto& o = receipt.options;
  const uint64_t deadline = admission ? admission->native_deadline_ms : GetTickCount64() + o.max_ms;
  require(GetTickCount64() < deadline, "CAMPAIGN_DEADLINE");
  if (o.operation == "capture") validate_output(o.output);
  receipt.devices = enumerate_metadata();
  if (o.operation == "inventory") return;
  // Match the exact opaque endpoint, then freshly resolve and compare the
  // reviewed unit/driver immediately before activation. Neither a friendly
  // name nor the enumerated endpoint alone establishes unit continuity.
  for (const auto& device : receipt.devices) if (device.endpoint == o.endpoint) selected = device.activate;
  require(selected != nullptr, "CAMERA_IDENTITY_NOT_PRESENT");
  require(admission.has_value(), "ACTIVATION_ADMISSION_REQUIRED");
  rocell::identity::WindowsIdentityMetadataApi identity_api;
  identity_gate.run(
      admission->identity.traits, admission->native_started_ms, deadline,
      {[]() { return static_cast<std::uint64_t>(GetTickCount64()); },
       // Cancellation is parent-owned process termination in this pipe protocol;
       // EOF has already closed the grant channel. No cooperative Stop signal
       // is claimed here. A wedged metadata/activation API remains parent-bounded.
       []() { return false; }},
      [&](const auto& limits, const auto& control) {
        return rocell::identity::resolve_identity_metadata(identity_api, o.endpoint, limits, control);
      },
      [&]() {
        require(attr_string(selected.Get(), MF_DEVSOURCE_ATTRIBUTE_SOURCE_TYPE_VIDCAP_SYMBOLIC_LINK)
                    == admission->identity.traits.endpoint, "CAMERA_ACTIVATION_ENDPOINT_CHANGED");
        require(GetTickCount64() < deadline, "CAMPAIGN_DEADLINE");
        ++receipt.activation_attempts; receipt.source_released = false;
        hrcheck(selected->ActivateObject(IID_PPV_ARGS(&source)), "CAMERA_ACTIVATION_FAILED");
        ++receipt.opened;
      });
  ComPtr<IMFAttributes> attributes;
  hrcheck(MFCreateAttributes(&attributes, 4), "READER_ATTRIBUTES_FAILED");
  hrcheck(attributes->SetUINT32(MF_READWRITE_DISABLE_CONVERTERS, TRUE), "READER_ATTRIBUTES_FAILED");
  hrcheck(attributes->SetUINT32(MF_SOURCE_READER_ENABLE_VIDEO_PROCESSING, FALSE), "READER_ATTRIBUTES_FAILED");
  callback.Attach(new Callback());
  hrcheck(attributes->SetUnknown(MF_SOURCE_READER_ASYNC_CALLBACK, callback.Get()), "READER_ATTRIBUTES_FAILED");
  hrcheck(MFCreateSourceReaderFromMediaSource(source.Get(), attributes.Get(), &reader), "SOURCE_READER_FAILED");
  hrcheck(reader->SetStreamSelection(kAllStreams, FALSE), "STREAM_SELECTION_FAILED");
  hrcheck(reader->SetStreamSelection(kFirstVideoStream, TRUE), "STREAM_SELECTION_FAILED");
  ComPtr<IMFMediaType> selected_type;
  for (DWORD index = 0; index <= 128; ++index) {
    ComPtr<IMFMediaType> type;
    const HRESULT result = reader->GetNativeMediaType(kFirstVideoStream, index, &type);
    if (result == MF_E_NO_MORE_TYPES) break;
    hrcheck(result, "NATIVE_MODE_ENUMERATION_FAILED");
    require(index < 128, "NATIVE_MODE_COUNT_LIMIT");
    Mode mode = read_mode(type.Get()); receipt.modes.push_back(mode);
    if (o.mode && mode.matches(*o.mode) && !selected_type) selected_type = type;
  }
  receipt.controls = controls_for(source.Get());
  if (o.operation == "probe") return;
  require(selected_type != nullptr, "REQUESTED_NATIVE_MODE_UNAVAILABLE");
  hrcheck(reader->SetCurrentMediaType(kFirstVideoStream, nullptr, selected_type.Get()), "NATIVE_MODE_SET_FAILED");
  ComPtr<IMFMediaType> current;
  hrcheck(reader->GetCurrentMediaType(kFirstVideoStream, &current), "NATIVE_MODE_READBACK_FAILED");
  receipt.observed = read_mode(current.Get());
  require(receipt.observed->matches(*o.mode), "NATIVE_MODE_READBACK_MISMATCH");
#ifdef ROCELL_ENABLE_OWNED_CAPTURE
  require(!o.mode->stride || receipt.observed->stride == o.mode->stride, "REQUESTED_MODE_STRIDE_MISMATCH");
#endif
  apply_controls(source.Get(), o.settings, receipt.controls, receipt.control_attempts);
  uint64_t total = 0;
  unsigned notifications = 0;
  while (receipt.frames.size() < o.frames) {
    require(GetTickCount64() < deadline && notifications < 4096, "CAMPAIGN_DEADLINE");
    callback->prepare();
    hrcheck(reader->ReadSample(kFirstVideoStream, 0, nullptr, nullptr, nullptr, nullptr), "READ_SAMPLE_REQUEST_FAILED");
    const uint64_t now = GetTickCount64();
    require(now < deadline, "CAMPAIGN_DEADLINE");
    require(WaitForSingleObject(callback->ready, static_cast<DWORD>(deadline - now)) == WAIT_OBJECT_0, "FRAME_DEADLINE");
    std::lock_guard<std::mutex> lock(callback->mutex);
    ++notifications;
    hrcheck(callback->status, "READ_SAMPLE_FAILED");
    require(!(callback->flags & (MF_SOURCE_READERF_ERROR | MF_SOURCE_READERF_ENDOFSTREAM |
      MF_SOURCE_READERF_CURRENTMEDIATYPECHANGED | MF_SOURCE_READERF_NATIVEMEDIATYPECHANGED)), "STREAM_CHANGED_OR_ENDED");
    if (!callback->sample) continue;
    ++receipt.received;
    receipt.frames.push_back(write_frame(callback->sample.Get(), *receipt.observed, o,
      static_cast<unsigned>(receipt.frames.size()), callback->timestamp, callback->arrival, total));
  }
}

} // namespace

#if defined(ROCELL_ACTIVATION_PROBE_ONLY) == defined(ROCELL_ACTIVATION_CAPTURE_ONLY)
#error Exactly one fixed activation purpose is required
#endif

int wmain(int argc, wchar_t** argv) {
#ifdef ROCELL_ACTIVATION_PROBE_ONLY
  constexpr auto purpose = rocell::activation_protocol::Purpose::Probe;
#else
  constexpr auto purpose = rocell::activation_protocol::Purpose::Capture;
#endif
  const std::vector<std::wstring> arguments(argv + 1, argv + argc);
  // This build has no inventory/identity/self-test/legacy command entry point.
  // Reject the other purpose before pipes, files, COM/MF or metadata work.
  if (!rocell::activation_launch::accepts(arguments, purpose)) {
    std::cerr << "EXACT_V2_PURPOSE_ARGUMENTS_REQUIRED\n"; return 2;
  }
  std::optional<rocell::activation_entry::Admitted> admission;
  try {
    admission.emplace(rocell::activation_entry::admit(
        std::vector<std::wstring>(arguments.begin() + 1, arguments.end()), purpose));
  } catch (const std::exception&) {
    std::cerr << "OWNED_V2_ADMISSION_FAILED\n"; return 2;
  }
  std::vector<std::wstring> operation_arguments;
  Receipt receipt;
  rocell::activation_gate::Gate identity_gate;
  bool com = false, mf = false;
  ComPtr<IMFActivate> selected;
  ComPtr<IMFMediaSource> source;
  ComPtr<IMFSourceReader> reader;
  ComPtr<Callback> callback;
  try {
    if (admission) {
      // After accepted RELEASE, every setup failure belongs to the versioned
      // result and cleanup path, including private-directory binding failure.
      // Before acceptance, no usable admitted result can be fabricated.
      receipt.options.operation = admission->purpose == rocell::activation_protocol::Purpose::Probe ? "probe" : "capture";
      receipt.options.endpoint = admission->identity.traits.endpoint;
      require(GetTickCount64() < admission->native_deadline_ms, "CAMPAIGN_DEADLINE");
      operation_arguments = rocell::activation_entry::operation_arguments(
          *admission, receipt.options.operation == "capture" ? fs::current_path().wstring() : L"");
    }
    receipt.options = parse_options(operation_arguments);
#ifdef ROCELL_ENABLE_OWNED_CAPTURE
    if (receipt.options.operation == "capture") {
      require(admission.has_value() && admission->state.admitted(), "OWNED_CAPTURE_ADMISSION_REQUIRED");
      const auto capture = rocell::capture_admission::parse_capture_settings(admission->state.request().fields.at("capture_json").text);
      receipt.options.mode->stride = capture.requested_stride;
      // Existing empty/non-reparse ancestry check now also runs BEFORE COM/MF.
      // The parent still owns directory handles and filesystem-race containment.
      validate_output(receipt.options.output);
    }
#endif
    if (admission) require(GetTickCount64() < admission->native_deadline_ms, "CAMPAIGN_DEADLINE");
    hrcheck(CoInitializeEx(nullptr, COINIT_MULTITHREADED), "COM_STARTUP_FAILED"); com = true;
    hrcheck(MFStartup(MF_VERSION, MFSTARTUP_LITE), "MF_STARTUP_FAILED"); mf = true;
    campaign(receipt, selected, source, reader, callback, admission, identity_gate);
  } catch (const Failure& e) { receipt.reason = e.what(); }
    catch (const rocell::activation_gate::Error& e) { receipt.reason = e.what(); }
    catch (const std::exception&) { receipt.reason = "NATIVE_UNEXPECTED_FAILURE"; }
  // No provider reference outlives its receipt. A wedged Shutdown/Release is
  // bounded by the Python process deadline and becomes uncertain, not success.
  NativeCleanupApi cleanup_api(receipt, selected, source, reader, callback);
  rocell::camera_cleanup::Cleanup cleanup;
  const auto& observed_cleanup = cleanup.run(
      {com, mf, receipt.activation_attempts != 0, selected != nullptr}, cleanup_api);
  receipt.shutdown_attempts = observed_cleanup.shutdown_attempts;
  receipt.shutdown_hr = observed_cleanup.shutdown_hr;
  receipt.source_released = observed_cleanup.references_released;
  receipt.mf_shutdown_hr = observed_cleanup.mf_shutdown_hr;
  receipt.com_uninitialized = observed_cleanup.com_uninitialized;
  // Preserve the acquisition's first error, while both cleanup HRESULTs remain
  // separately visible in the existing strict receipt. No schema is weakened.
  if (receipt.reason.empty() && observed_cleanup.first_failure)
    receipt.reason = observed_cleanup.first_failure;
  const auto result = admission
      ? rocell::activation_entry::wrap_result(*admission, identity_gate.record(), receipt.json())
      : receipt.json();
  if (result.size() > 256 * 1024) { std::cerr << "RECEIPT_LIMIT\n"; return 2; }
  std::cout << result << '\n';
  return receipt.reason.empty() ? 0 : 1;
}
