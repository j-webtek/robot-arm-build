#pragma once
#include "admission_protocol.h"
#include <vector>

namespace rocell::admission {
// Production inherited-pipe entry. Throws before COM/MF on every missing,
// malformed, repeated, late or unbound grant. No test bypass or activation flag.
AdmissionState admit_owned_probe(const std::vector<std::wstring>& arguments);
std::wstring endpoint_wide(const AdmissionState& admission);
std::string wrap_native_result(const AdmissionState& admission, const std::string& native_json);
}
