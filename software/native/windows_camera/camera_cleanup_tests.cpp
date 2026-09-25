// No production adapter, camera_worker, Win32, COM or Media Foundation is
// compiled/linked into this executable. Test the same sequencing as production;
// successful fake calls are expressly not a camera/driver qualification.
#include <iostream>
#include <string>
#include <vector>

#include "camera_cleanup.h"

namespace {
using namespace rocell::camera_cleanup;
unsigned assertions = 0;
void check(bool condition, const char* label) {
  ++assertions;
  if (!condition) throw std::runtime_error(label);
}

class Recorder final : public Api {
 public:
  std::vector<std::string> calls;
  std::string throw_at;
  std::int32_t source_hr = 0, mf_hr = 0;
  void call(const char* name) {
    calls.emplace_back(name);
    if (throw_at == name) throw std::runtime_error("MODELED_INTERRUPTION");
  }
  std::int32_t shutdown_activation() override {
    call("shutdown");
    return source_hr;
  }
  void release_reader() override { call("reader"); }
  void release_callback() override { call("callback"); }
  void release_source() override { call("source"); }
  void release_activation() override { call("activation"); }
  void release_enumerated_activations() override { call("inventory"); }
  std::int32_t shutdown_media_foundation() override {
    call("mf");
    return mf_hr;
  }
  void uninitialize_com() override { call("com"); }
};

const std::vector<std::string> releases{"reader", "callback", "source", "activation",
                                        "inventory"};
const std::vector<std::string> full{"shutdown",   "reader",    "callback", "source",
                                    "activation", "inventory", "mf",       "com"};

void no_replay(Cleanup& cleanup, const Started& started, Recorder& api) {
  const auto before = api.calls;
  bool denied = false;
  try {
    cleanup.run(started, api);
  } catch (const std::logic_error& error) {
    denied = std::string(error.what()) == "CAMERA_CLEANUP_ALREADY_ATTEMPTED";
  }
  check(denied && api.calls == before, "cleanup replay performed calls");
}

void partial_startup() {
  // Admission/parse failure; COM startup failure; MF startup failure; inventory
  // or endpoint failure; attempted activation (including a failed ActivateObject).
  for (const Started started : std::vector<Started>{{},
                                                    {true, false, false, false},
                                                    {true, true, false, false},
                                                    {true, true, false, true},
                                                    {true, true, true, true}}) {
    Recorder api;
    Cleanup cleanup;
    const auto& observed = cleanup.run(started, api);
    auto expected = releases;
    if (started.activation_attempted) expected.insert(expected.begin(), "shutdown");
    if (started.media_foundation) expected.push_back("mf");
    if (started.com) expected.push_back("com");
    check(api.calls == expected, "partial startup cleanup order");
    check(observed.shutdown_attempts == (started.activation_attempted ? 1U : 0U),
          "shutdown attempts");
    check(observed.shutdown_hr.has_value() == started.activation_attempted,
          "invented shutdown result");
    check(observed.mf_shutdown_hr.has_value() == started.media_foundation,
          "invented MF result");
    check(observed.references_released && observed.com_uninitialized == started.com,
          "cleanup completion mismatch");
    check(observed.first_failure == nullptr, "invented cleanup error");
    no_replay(cleanup, started, api);
  }
}

void returned_errors() {
  const Started started{true, true, true, true};
  // Both HRESULTs are signed 32-bit, including ordinary nonzero success. Never
  // conflate a successful function return with the receipt's stricter S_OK rule.
  for (const std::int32_t source_hr : {0, 1, -2147467259}) {
    for (const std::int32_t mf_hr : {0, 1, -2147467259}) {
      Recorder api;
      api.source_hr = source_hr;
      api.mf_hr = mf_hr;
      Cleanup cleanup;
      const auto& observed = cleanup.run(started, api);
      check(api.calls == full, "HRESULT failure skipped remaining cleanup");
      check(observed.shutdown_hr == source_hr && observed.mf_shutdown_hr == mf_hr,
            "HRESULT changed");
      check(observed.shutdown_attempts == 1 && observed.references_released &&
                observed.com_uninitialized,
            "incomplete returned cleanup");
      const std::string reason = observed.first_failure ? observed.first_failure : "";
      check(reason == (source_hr < 0 ? "SOURCE_SHUTDOWN_FAILED"
                       : mf_hr < 0   ? "MF_SHUTDOWN_FAILED"
                                     : ""),
            "first cleanup failure replaced");
      no_replay(cleanup, started, api);
    }
  }
}

void interrupted_calls() {
  const Started started{true, true, true, true};
  for (std::size_t index = 0; index < full.size(); ++index) {
    Recorder api;
    api.throw_at = full[index];
    Cleanup cleanup;
    bool interrupted = false;
    try {
      cleanup.run(started, api);
    } catch (const std::runtime_error& error) {
      interrupted = std::string(error.what()) == "MODELED_INTERRUPTION";
    }
    check(interrupted, "interrupted cleanup returned completion");
    check(api.calls == std::vector<std::string>(full.begin(), full.begin() + index + 1),
          "calls after interruption");
    const auto& observed = cleanup.observed();
    check(observed.shutdown_attempts == 1, "lost attempted shutdown");
    check(observed.shutdown_hr.has_value() == (index > 0), "invented shutdown return");
    check(observed.references_released == (index >= 6),
          "premature reference release completion");
    check(observed.mf_shutdown_hr.has_value() == (index > 6), "invented MF return");
    check(!observed.com_uninitialized, "premature COM completion");
    no_replay(cleanup, started, api);
  }
}

void missing_activation() {
  const Started started{true, true, true, false};
  Recorder api;
  api.mf_hr = -2147467259;
  Cleanup cleanup;
  const auto& observed = cleanup.run(started, api);
  auto expected = releases;
  expected.push_back("mf");
  expected.push_back("com");
  check(api.calls == expected, "missing activation tried shutdown or skipped releases");
  check(observed.shutdown_attempts == 0 && !observed.shutdown_hr,
        "missing activation invented result");
  check(std::string(observed.first_failure) == "SOURCE_SHUTDOWN_UNAVAILABLE",
        "missing activation hidden by MF failure");
  no_replay(cleanup, started, api);
}
}  // namespace

int main() {
  try {
    partial_startup();
    returned_errors();
    interrupted_calls();
    missing_activation();
    std::cout << "PASS: " << assertions << " hardware-incapable cleanup assertions\n";
    return 0;
  } catch (const std::exception& error) {
    std::cerr << error.what() << '\n';
    return 1;
  }
}
