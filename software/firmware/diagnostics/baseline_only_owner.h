// Queue acquisition separately from request handling; never starts a listener
// or accesses policy/key files. Motion ingress must share the same session gate.
#pragma once
#include "baseline_only_json.h"
#include "diagnostic_session_claim.h"
namespace rocell_diag {
enum class BaselineState { Idle, Queued, Running, Captured, Fault };
template<class Library,class Clock>
class BaselineOnlyOwner {
 public:
  BaselineOnlyOwner(Library& library,Clock& clock,DiagnosticSessionClaim& claim,
                    const char* boot):library_(library),clock_(clock),claim_(claim) {
    if(valid_identity(boot)){memcpy(boot_,boot,strlen(boot)+1);}else state_=BaselineState::Fault;
  }
  bool request(const char* boot,const char* scan) {
    if(state_!=BaselineState::Idle || !valid_identity(boot) ||
       !valid_identity(scan) || strcmp(boot_,boot))return false;
    if(!claim_.claim(DiagnosticClaim::Baseline))return false;
    memcpy(scan_,scan,strlen(scan)+1);state_=BaselineState::Queued;return true;
  }
  void poll() {
    if(state_!=BaselineState::Queued)return;
    state_=BaselineState::Running;
    const bool complete=scan_data_.run(library_,clock_,1000000,7000000);
    const bool encoded=baseline_only_json(scan_data_,boot_,scan_,json_,sizeof(json_));
    state_=complete&&encoded?BaselineState::Captured:BaselineState::Fault;
    if(!encoded){json_[0]=0;encoding_failed_=true;}
  }
  BaselineState state() const{return state_;}
  const char* record() const{return json_;}
  const char* reason() const{return encoding_failed_?"BASELINE_EXPORT_FAILED":scan_data_.reason();}
 private:
  Library& library_;Clock& clock_;DiagnosticSessionClaim& claim_;
  char boot_[129]={},scan_[129]={},json_[2304]={};
  BaselineState state_=BaselineState::Idle;bool encoding_failed_=false;
  BaselineOnlyScan scan_data_;
};
}
