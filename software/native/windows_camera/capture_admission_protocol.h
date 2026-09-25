#pragma once
#include "admission_protocol.h"
#include <optional>
#include <vector>

// Pure capture-specific extension. Old probe parsing remains independently
// strict; no field-count increase, filesystem access or device APIs here.
namespace rocell::capture_admission {
inline constexpr std::uint32_t admission_timeout_ms = 5000;
inline constexpr std::uint32_t native_duration_ms = 5000;
struct CaptureSettings {
  admission::Fields fields;
  std::uint32_t width = 0, height = 0, fps_numerator = 0, fps_denominator = 0;
  std::uint32_t frame_count = 0;
  std::uint64_t max_frame_bytes = 0, max_total_bytes = 0;
  std::optional<std::int32_t> requested_stride;
  std::string output_directory, controls;
};
CaptureSettings parse_capture_settings(const std::string& canonical_json);
admission::Request parse_request(const std::string& payload, const std::string& expected_hash);
// Reconstruct only from an admitted request and the caller's exact current cwd.
// These arguments are internal data, never an additional public command surface.
std::vector<std::wstring> capture_arguments(const admission::AdmissionState&, const std::wstring& cwd);
}
