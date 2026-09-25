// Offline integration candidate: no routes, hardware I/O or startup side effects.
// Keep the session and this owner off the control-task stack. All callers must
// serialize on that task and honor the same bus reservation before dispatch.
#pragma once
#include "start_envelope.h"
#include "shoulder_preload_session.h"
#include <cstdio>
namespace rocell_diag {
class ShoulderBusReservation {
 public:
  bool reserve(){if(reserved_)return false;reserved_=true;return true;}
  bool reserved()const{return reserved_;}
 private:
  // Deliberately no automatic release on failure: a partly initialized pair
  // must not silently become available to another command owner.
  bool reserved_=false;
};

class ShoulderAuthorizedStart {
 public:
  ShoulderAuthorizedStart(const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,
      const char* command,ShoulderSessionScope approved)
      :gate_(key,boot,nonce,issued,expires),expires_(expires),scope_(approved){
    static const char hex[]="0123456789abcdef";
    for(unsigned i=0;i<16;++i){boot_[2*i]=hex[boot[i]>>4];boot_[2*i+1]=hex[boot[i]&15];}
    // Restricted identifiers make the controller-built canonical JSON exact;
    // no caller-defined targets, speeds or scope extensions are accepted.
    if(!command||!command[0]||strlen(command)>128)return;
    for(const char* p=command;*p;++p)
      if(!((*p>='a'&&*p<='z')||(*p>='A'&&*p<='Z')||(*p>='0'&&*p<='9')||*p=='-'||*p=='_'))return;
    if(approved!=ShoulderSessionScope::PreloadOnly&&approved!=ShoulderSessionScope::PairHold&&approved!=ShoulderSessionScope::MixedTarget&&approved!=ShoulderSessionScope::PosePreparation&&approved!=ShoulderSessionScope::ShoulderRise&&approved!=ShoulderSessionScope::ClearanceRecovery&&approved!=ShoulderSessionScope::StableClearanceRecovery)return;
    strcpy(command_,command);
    const int n=snprintf(plan_,sizeof(plan_),
      "{\"schema\":\"rocell.shoulder_start.v1\",\"boot_id\":\"%s\",\"command_id\":\"%s\",\"scope\":\"%s\"}",
      boot_,command_,approved==ShoulderSessionScope::StableClearanceRecovery?"STABLE_CLEARANCE_RECOVERY":approved==ShoulderSessionScope::ClearanceRecovery?"CLEARANCE_RECOVERY":approved==ShoulderSessionScope::ShoulderRise?"SHOULDER_RISE":approved==ShoulderSessionScope::PosePreparation?"POSE_PREPARATION":approved==ShoulderSessionScope::MixedTarget?"MIXED_TARGET":approved==ShoulderSessionScope::PairHold?"PAIR_HOLD":"PRELOAD_ONLY");
    valid_=n>0&&size_t(n)<sizeof(plan_);
  }
  const char* canonical_plan()const{return valid_?plan_:nullptr;}
  const char* reason()const{return reason_;}
  template<class Clock,class Crypto,class Admission,class Starter>
  bool start(const uint8_t* token,size_t size,Clock& clock,Crypto& crypto,
      ShoulderBusReservation& bus,Admission& admission,Starter& starter){
    if(attempted_)return false;
    attempted_=true;
    AuthenticatedPlanView view;const auto begin=clock.now_us();
    if(!valid_||!gate_.consume(token,size,begin,crypto,view))return fail("AUTHENTICATION_REJECTED");
    if(view.length!=strlen(plan_)||memcmp(view.bytes,plan_,view.length))return fail("PLAN_REJECTED");
    if(!bus.reserve())return fail("BUS_RESERVED");
    // Authentication is NOT physical admission. This callback must perform
    // the separately reviewed fresh-state/clearance check, without mutations.
    if(!admission())return fail("ADMISSION_REJECTED");
    const auto now=clock.now_us();
    if(now<begin||now>=expires_)return fail("EXPIRED_BEFORE_START");
    // Starter may only activate the pre-reviewed session, never advance it.
    // The first actual target write remains gated by its exported intent.
    if(!starter(boot_,command_,scope_))return fail("SESSION_ACTIVATION_FAILED");
    reason_="SESSION_ACTIVATED";return true;
  }
 private:
  bool fail(const char* reason){reason_=reason;return false;}
  StartEnvelopeGate gate_;uint64_t expires_;
  ShoulderSessionScope scope_;
  bool valid_=false,attempted_=false;
  char boot_[33]={},command_[129]={},plan_[320]={};
  const char* reason_="NOT_STARTED";
};
}
