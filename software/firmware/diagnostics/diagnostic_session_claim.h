// Single-main-loop arbitration. No release/re-arm; reboot starts a new session.
// Not a mutex for concurrent tasks: all participating ingress must use this gate.
#pragma once
namespace rocell_diag {
enum class DiagnosticClaim { Unclaimed, Baseline, Motion };
class DiagnosticSessionClaim {
 public:
  bool claim(DiagnosticClaim kind) {
    if(kind==DiagnosticClaim::Unclaimed || state_!=DiagnosticClaim::Unclaimed)return false;
    state_=kind;return true;
  }
  DiagnosticClaim state() const{return state_;}
 private:
  DiagnosticClaim state_=DiagnosticClaim::Unclaimed;
};
}
