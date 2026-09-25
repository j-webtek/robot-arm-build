#pragma once
#include <vector>

#include "camera_activation_gate.h"
#include "camera_activation_protocol.h"

namespace rocell::activation_entry {
struct Admitted {
  admission::AdmissionState state;
  activation_protocol::ExpectedIdentity identity;
  activation_protocol::Purpose purpose;
  std::uint64_t native_started_ms, native_deadline_ms;
};

// The only active entry for this new draft worker. Inherited pipes, exact v2
// request, fresh challenge, one bound RELEASE and EOF precede COM/MF startup.
Admitted admit(const std::vector<std::wstring>& arguments,
               activation_protocol::Purpose purpose);
std::vector<std::wstring> operation_arguments(const Admitted&, const std::wstring& cwd);
std::string wrap_result(const Admitted&, const activation_gate::Record&,
                        const std::string& native_receipt);
}  // namespace rocell::activation_entry
