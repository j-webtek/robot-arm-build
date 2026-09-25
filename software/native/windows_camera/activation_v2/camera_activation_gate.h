#pragma once
// Shared pre-open order. No OS/device/process/file implementation is linked by
// this header. The worker supplies the real resolver and activation callback.
#include <functional>
#include <optional>
#include <stdexcept>

#include "camera_activation_identity.h"

namespace rocell::activation_gate {
class Error : public std::runtime_error {
 public:
  explicit Error(const char* code) : std::runtime_error(code) {}
};

struct Record {
  bool attempted = false;
  bool resolution_attempted = false;
  bool resolution_returned = false;
  bool activation_callback_entered = false;
  identity::Limits limits;
  std::optional<std::uint64_t> observation_started_ms, observation_returned_ms;
  std::optional<identity::IdentityMetadata> metadata;
  std::optional<activation_identity::Result> comparison;
};

class Gate {
 public:
  using Resolver = std::function<identity::IdentityMetadata(const identity::Limits&,
                                                            const identity::RunControl&)>;

  const Record& record() const { return record_; }

  void run(const activation_identity::Expected& expected, std::uint64_t started_ms,
           std::uint64_t deadline_ms, const identity::RunControl& control,
           const Resolver& resolve, const std::function<void()>& activate) {
    if (record_.attempted) throw Error("ACTIVATION_GUARD_ALREADY_ATTEMPTED");
    record_.attempted = true;  // A failed call never becomes replayable.
    if (!activation_identity::expectation_valid(expected) || !control.monotonic_ms ||
        !control.cancelled || !resolve || !activate || deadline_ms <= started_ms ||
        deadline_ms - started_ms != 5000)
      throw Error("ACTIVATION_GUARD_CONTEXT_INVALID");

    std::uint64_t last = started_ms;
    auto check = [&]() {
      if (control.cancelled()) throw Error("ACTIVATION_GUARD_CANCELLED");
      const auto now = control.monotonic_ms();
      if (now < last) throw Error("ACTIVATION_GUARD_CLOCK_CHANGED");
      last = now;
      if (now >= deadline_ms) throw Error("ACTIVATION_GUARD_DEADLINE");
      return now;
    };
    const auto before = check();
    // The existing parent identity-receipt contract accepts 100..30000 ms.
    // Do not launch an observation whose remaining budget cannot be represented
    // by that unchanged contract, and do not round the budget up past deadline.
    if (deadline_ms - before < 100) throw Error("ACTIVATION_IDENTITY_BUDGET_INSUFFICIENT");
    record_.observation_started_ms = before;
    // Only the remaining native budget is offered to metadata resolution.
    // The original deadline is checked again before any activation callback.
    // Parent-owned process termination must still bound a wedged OS API.
    record_.limits.duration_ms = static_cast<std::uint32_t>(deadline_ms - before);
    record_.limits.max_parent_nodes = 16;
    record_.resolution_attempted = true;
    record_.metadata = resolve(record_.limits, control);
    record_.resolution_returned = true;
    record_.observation_returned_ms = check();
    record_.comparison = activation_identity::compare(expected, *record_.metadata);
    if (*record_.comparison != activation_identity::Result::Match)
      throw Error("ACTIVATION_IDENTITY_COMPARISON_FAILED");
    check();
    // Callback entry is not an OS activation count. The native receipt counts
    // the actual call separately, including a failure in the callback's own
    // final endpoint/deadline check before it reaches ActivateObject.
    record_.activation_callback_entered = true;
    activate();
  }

 private:
  Record record_;
};
}  // namespace rocell::activation_gate
