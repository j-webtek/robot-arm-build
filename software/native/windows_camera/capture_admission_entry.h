#pragma once
#include "capture_admission_protocol.h"

namespace rocell::capture_admission {
// Explicit inherited-pipe capture entry; no COM/MF or filesystem effects.
// It consumes one hash/challenge-bound RELEASE and EOF within five seconds.
admission::AdmissionState admit_owned_capture(const std::vector<std::wstring>& arguments);
}
