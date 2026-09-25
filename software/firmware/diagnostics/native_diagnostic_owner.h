// Included after the reference arm module, before command ingresses.
// Internal candidate API only: no HTTP/serial start command is registered.
#pragma once
#define ROCELL_NATIVE_DIAGNOSTIC_OWNER 1
#include <esp_timer.h>
#include "received_session.h"
#include "evidence_store.h"
#include "reference_elbow_admission.h"
#include "fresh_elbow_baseline.h"
rocell_diag::ReceivedSession rocellDiagnosticSession;
rocell_diag::EvidenceStore<16> rocellDiagnosticEvidence;
char rocellDiagnosticInstance[33]={};
bool rocellDiagnosticOwned=false;
bool rocellOwnerFault();
struct RocellNativeClock {uint64_t now_us(){return static_cast<uint64_t>(esp_timer_get_time());}};
struct RocellBaselinePolicy {
  uint16_t maximum_delta,settled_tolerance;
  uint64_t maximum_pair_us,maximum_age_us;
};
class RocellFreshAdmission {
 public:
  RocellFreshAdmission(rocell_diag::ElbowAdmissionBounds bounds,RocellBaselinePolicy policy,const char* command)
      :converter_(bounds),policy_(policy),command_(command) {}
  bool admit_and_convert(double rad,uint16_t speed,uint8_t acceleration,uint16_t& target) {
    if(!converter_.admit_and_convert(rad,speed,acceleration,target))return false;
    RocellNativeClock clock;
    const bool accepted=baseline_.check(st,clock,target,policy_.maximum_delta,policy_.settled_tolerance,
                                      policy_.maximum_pair_us,policy_.maximum_age_us);
    if(!baseline_.encode(rocellDiagnosticInstance,command_,pair_,sizeof(pair_)))return false;
    const int n=snprintf(report_,sizeof(report_),
        "{\"schema\":\"rocell.elbow_baseline.v1\",\"accepted\":%s,\"reason\":\"%s\","
        "\"maximum_delta_counts\":%u,\"settled_tolerance_counts\":%u,"
        "\"maximum_pair_us\":%llu,\"maximum_age_us\":%llu,\"acquisition\":%s}",
        accepted?"true":"false",baseline_.reason(),policy_.maximum_delta,policy_.settled_tolerance,
        (unsigned long long)policy_.maximum_pair_us,(unsigned long long)policy_.maximum_age_us,pair_);
    if(n<0 || static_cast<size_t>(n)>=sizeof(report_) || !rocellDiagnosticEvidence.publish("baseline",report_))return false;
    const uint64_t now=clock.now_us();
    return accepted && !rocellOwnerFault() && now>=baseline_.finished_us() &&
        now-baseline_.finished_us()<=policy_.maximum_age_us;
  }
 private:
  rocell_diag::ReferenceElbowAdmission converter_;
  const RocellBaselinePolicy policy_;const char* command_;
  rocell_diag::FreshElbowBaseline baseline_;
  char pair_[1536],report_[2048];
};

bool rocellRejectDiagnosticInterference() {
  if(!rocellDiagnosticOwned)return false;
  rocellDiagnosticSession.interference();return true;
}

// Caller must provide clearance admission and authenticated command
// identity before invoking this API. Bounds alone do not establish those facts.
bool startReceivedDiagnostic(const char* command,const char* payload,size_t length,
    rocell_diag::ElbowAdmissionBounds bounds,uint16_t samples,uint64_t pair_budget,
    uint64_t interval_us,RocellBaselinePolicy baseline_policy) {
  if(rocellDiagnosticOwned){rocellDiagnosticSession.interference();return false;}
  if(rocellOwnerFault() || !rocellDiagnosticInstance[0])return false;
  rocellDiagnosticOwned=true; // Never release automatically, including on failure.
  if(!samples || samples>10 || !rocellDiagnosticEvidence.reserve(static_cast<size_t>(samples)+6)) {
    rocellDiagnosticSession.export_failed();return false;
  }
  RocellNativeClock clock;RocellFreshAdmission admission(bounds,baseline_policy,command);
  return rocellDiagnosticSession.start(st,clock,rocellDiagnosticEvidence,admission,
      rocellDiagnosticInstance,command,payload,length,samples,pair_budget,interval_us);
}

void pollReceivedDiagnostic() {
  if(!rocellDiagnosticOwned)return;
  if(rocellOwnerFault()){rocellDiagnosticSession.interference();return;}
  RocellNativeClock clock;
  rocellDiagnosticSession.sample(st,clock,rocellDiagnosticEvidence);
}
