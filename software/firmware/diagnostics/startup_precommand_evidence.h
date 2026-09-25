// Read-only composition for a separately authenticated startup command path.
// Does not authenticate a request or dispatch. Caller supplies sole bus ownership.
#pragma once
#include "startup_position_baseline.h"
#include "servo_control_state_read.h"
#include "baseline_only_json.h"
namespace rocell_diag {
inline bool control_state_json(const ServoControlStateRead& control,const char* boot,
                               const char* command,char* output,size_t capacity){
  if(!output||!capacity)return false;output[0]=0;
  if(!valid_identity(boot)||!valid_identity(command))return false;
  JsonDocument doc;doc["schema"]="rocell.control_state_reads.v1";
  doc["boot_id"]=boot;doc["command_id"]=command;
  doc["profile_id"]="waveshare-sms-sts-reference-b8b377642b3e";
  doc["reason"]=control.reason();auto rows=doc["reads"].to<JsonArray>();
  for(size_t i=0;const auto* read=control.read(i);++i){
    auto row=rows.add<JsonArray>();row.add(read->servo_id);row.add(read->address);
    whole_arm_read_json(row.add<JsonArray>(),*read);
  }
  if(doc.overflowed()||measureJson(doc)>=capacity)return false;
  return serializeJson(doc,output,capacity)>0;
}
enum class StartupEvidenceState { New, Acquiring, Bound, Fault };
template<class Library,class Clock,class Sink>
class StartupPrecommandEvidence {
 public:
  StartupPrecommandEvidence(Library& library,Clock& clock,Sink& sink,
      const StartupPositionPolicy& policy,uint8_t reviewed_mode)
      :library_(library),clock_(clock),sink_(sink),baseline_(policy),mode_(reviewed_mode),age_(policy.maximum_age_us){}
  bool begin(const char* boot,const char* command,uint16_t target,uint16_t delta){
    if(state_!=StartupEvidenceState::New)return false;
    state_=StartupEvidenceState::Acquiring;
    if(!valid_identity(boot)||!valid_identity(command)||!delta||delta>64||target<1024||target>3071)
      return fail("STARTUP_REQUEST_INVALID");
    memcpy(boot_,boot,strlen(boot)+1);memcpy(command_,command,strlen(command)+1);
    target_=target;delta_=delta;
    if(!sink_.reserve(3))return fail("STARTUP_EVIDENCE_FAILURE");
    return true;
  }
  void poll(){
    if(state_!=StartupEvidenceState::Acquiring)return;
    if(sink_.faulted()){fail("STARTUP_EVIDENCE_FAILURE");return;}
    baseline_.poll(library_,clock_);
    for(size_t i=published_;i<2;++i){
      const auto* scan=baseline_.scan(i);if(!scan)break;
      if(!baseline_only_json(*scan,boot_,command_,buffer_,sizeof(buffer_))||
         !sink_.publish(i?"startup_second":"startup_first",buffer_)){
        fail("STARTUP_EVIDENCE_FAILURE");return;
      }
      ++published_;
    }
    if(baseline_.state()==StartupPositionState::Fault){fail(baseline_.reason());return;}
    if(baseline_.state()!=StartupPositionState::Observed)return;
    const bool acquired=control_.acquire(library_,clock_);
    const uint64_t now=clock_.now_us();
    const bool matched=acquired&&control_.matches(mode_,now,age_);
    if(!control_state_json(control_,boot_,command_,buffer_,sizeof(buffer_))||
       !sink_.publish("startup_control",buffer_)){fail("STARTUP_EVIDENCE_FAILURE");return;}
    if(!matched){fail(control_.reason());return;}
    if(!baseline_.bind_elbow_target(target_,delta_,clock_.now_us())){fail(baseline_.reason());return;}
    state_=StartupEvidenceState::Bound;reason_="STARTUP_TARGET_BOUND";
  }
  // Must be called at the actual write boundary by the authenticated owner.
  // A true return is not independently permission to write.
  bool boundary(uint16_t converted_target,uint64_t now){
    if(state_!=StartupEvidenceState::Bound)return false;
    if(sink_.faulted()||converted_target!=target_||!baseline_.fresh(now)||!control_.matches(mode_,now,age_))
      return fail("STARTUP_BOUNDARY_REJECTED");
    return true;
  }
  StartupEvidenceState state()const{return state_;}
  const char* reason()const{return reason_;}
 private:
  bool fail(const char* reason){state_=StartupEvidenceState::Fault;reason_=reason;return false;}
  Library& library_;Clock& clock_;Sink& sink_;StartupPositionBaseline baseline_;ServoControlStateRead control_;
  uint8_t mode_;uint64_t age_;uint16_t target_=0,delta_=0;size_t published_=0;
  char boot_[129]={},command_[129]={},buffer_[2304]={};
  StartupEvidenceState state_=StartupEvidenceState::New;const char* reason_="NOT_STARTED";
};
}
