// Shared cleanup choreography only. This header has no Windows, COM, MF,
// endpoint, process-launch or file APIs. The production adapter owns those
// references; incapable tests supply a recorder with no device implementation.
#pragma once

#include <cstdint>
#include <optional>
#include <stdexcept>

namespace rocell::camera_cleanup {

struct Started {
  bool com = false;
  bool media_foundation = false;
  bool activation_attempted = false;
  bool activation_available = false;
};

struct Observation {
  unsigned shutdown_attempts = 0;
  std::optional<std::int32_t> shutdown_hr;
  std::optional<std::int32_t> mf_shutdown_hr;
  bool references_released = false;
  bool com_uninitialized = false;
  const char* first_failure = nullptr;
};

// Separate release methods make the ordering observable. A returned HRESULT
// failure still permits reference cleanup; a throwing/wedged call does not
// manufacture completion. The existing parent process deadline owns that case.
class Api {
 public:
  virtual ~Api() = default;
  virtual std::int32_t shutdown_activation() = 0;
  virtual void release_reader() = 0;
  virtual void release_callback() = 0;
  virtual void release_source() = 0;
  virtual void release_activation() = 0;
  virtual void release_enumerated_activations() = 0;
  virtual std::int32_t shutdown_media_foundation() = 0;
  virtual void uninitialize_com() = 0;
};

class Cleanup final {
 public:
  Cleanup() = default;
  Cleanup(const Cleanup&) = delete;
  Cleanup& operator=(const Cleanup&) = delete;

  // Explicit, once-only cleanup, never destructor-triggered or retried. The
  // outcome describes completed calls, not driver behavior or physical power.
  const Observation& run(const Started& started, Api& api) {
    if (used_) throw std::logic_error("CAMERA_CLEANUP_ALREADY_ATTEMPTED");
    used_ = true;
    if (started.activation_attempted && started.activation_available) {
      ++observation_.shutdown_attempts;  // Record attempt before a fallible call.
      observation_.shutdown_hr = api.shutdown_activation();
      if (*observation_.shutdown_hr < 0) observation_.first_failure = "SOURCE_SHUTDOWN_FAILED";
    } else if (started.activation_attempted) {
      observation_.first_failure = "SOURCE_SHUTDOWN_UNAVAILABLE";
    }
    api.release_reader();
    api.release_callback();
    api.release_source();
    api.release_activation();
    api.release_enumerated_activations();
    observation_.references_released = true;
    if (started.media_foundation) {
      observation_.mf_shutdown_hr = api.shutdown_media_foundation();
      if (*observation_.mf_shutdown_hr < 0 && !observation_.first_failure)
        observation_.first_failure = "MF_SHUTDOWN_FAILED";
    }
    if (started.com) {
      api.uninitialize_com();
      observation_.com_uninitialized = true;
    }
    return observation_;
  }

  const Observation& observed() const noexcept { return observation_; }

 private:
  bool used_ = false;
  Observation observation_;
};
}  // namespace rocell::camera_cleanup
