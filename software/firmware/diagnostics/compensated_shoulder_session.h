// Uninstalled integration candidate. Caller owns sticky bus reservation and
// physical admission; run on one control task, allocate off its stack.
#pragma once
#include "compensated_shoulder_authorization.h"
#include "shoulder_preload_session.h"
#include "shoulder_export_receipt.h"
namespace rocell_diag {
enum class CompensatedStepPhase { Capture, Waiting, Authorization, Intent, Write, Observe, Complete, Fault };
template<class Crypto> class CompensatedShoulderStepSession {
 public:
  CompensatedShoulderStepSession(Crypto& crypto,const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,const char* command)
      :auth_(key,boot,nonce,issued,expires,command),verifier_(crypto,key,boot,command),
       barrier_(crypto,verifier_),crypto_(crypto){
    if(!valid_identity(command)||strlen(command)>100){fail("IDENTITY_INVALID");return;}
    strcpy(command_,command);const char* hex="0123456789abcdef";
    for(int i=0;i<16;++i){boot_[i*2]=hex[boot[i]>>4];boot_[i*2+1]=hex[boot[i]&15];}
  }
  bool authorize(const uint8_t* bytes,size_t size,uint64_t now){
    if(phase_!=CompensatedStepPhase::Authorization){fail("AUTHORIZATION_PHASE");return false;}
    const char* records[3]={references_[0],references_[1],references_[2]};
    if(!auth_.verify(bytes,size,now,crypto_,records,reference_sizes_)){fail("PLAN_REJECTED");return false;}
    phase_=CompensatedStepPhase::Intent;return true;
  }
  bool receipt(const ShoulderReceiptView& token,uint64_t now){
    if(phase_!=CompensatedStepPhase::Waiting||!barrier_.accept(token,now)||!barrier_.consume()){
      fail("EXPORT_REJECTED");return false;
    }
    ++sequence_;phase_=next_;
    if(phase_==CompensatedStepPhase::Complete)reason_="COMPENSATED_STEP_OBSERVED";
    return true;
  }
  template<class Bus,class Clock,class Admission>
  void advance(Bus& bus,Clock& clock,Admission& admitted){
    using P=CompensatedStepPhase;
    if(phase_==P::Complete||phase_==P::Fault)return;
    if(bus.End!=0||!admitted()){fail("ADMISSION_LOST");return;}
    auto now=clock.now_us();
    if(phase_==P::Waiting){barrier_.poll(now);if(barrier_.state()==ShoulderExportState::Fault)fail("EXPORT_TIMEOUT");return;}
    if(phase_==P::Authorization)return;
    if(last_finished_&&(now<last_finished_)){fail("CLOCK_REVERSED");return;}
    if((phase_==P::Capture||phase_==P::Observe)&&last_finished_&&now-last_finished_<100000)return;
    ShoulderPreloadPose pose;
    if(!ShoulderPreloadCandidate::sample(bus,clock,pose,admitted)){fail("FEEDBACK_INVALID");return;}
    last_finished_=pose.finished_us;
    if(phase_==P::Capture){
      if(!LocalShoulderStepContract::stationary(pose)){fault_pose("BASELINE_MOVING",pose,clock.now_us());return;}
      publish(captured_?"BASELINE_STABILITY":"BASELINE",pose,captured_==2?P::Authorization:P::Capture,clock.now_us());
      if(phase_==P::Fault)return;
      reference_sizes_[captured_]=strlen(record());strcpy(references_[captured_],record());++captured_;return;
    }
    const auto* contract=auth_.contract();if(!contract){fail("NO_VERIFIED_PLAN");return;}
    for(int i=0;i<2;++i)pose.requested_pair[i]=contract->command_goals[i];
    if(phase_==P::Intent||phase_==P::Write){
      if(!contract->prewrite(pose,clock.now_us())){fault_pose("PREWRITE_CHANGED",pose,clock.now_us());return;}
      if(phase_==P::Intent){publish("SHOULDER_STEP_INTENT",pose,P::Write,clock.now_us());return;}
      if(writes_||!admitted()){fail("WRITE_NOT_ADMITTED");return;}
      uint8_t ids[2]={12,13},acc[2]={1,1};uint16_t speeds[2]={20,20};
      int16_t targets[2]={int16_t(contract->command_goals[0]),int16_t(contract->command_goals[1])};
      ++writes_;pose.action_started_us=clock.now_us();
      bus.SyncWritePosEx(ids,2,targets,speeds,acc); // Unacknowledged; never retry.
      sent_=pose.action_finished_us=clock.now_us();
      publish("SHOULDER_STEP_SENT",pose,P::Observe,clock.now_us());return;
    }
    if(pose.started_us<=sent_||pose.finished_us-sent_>5000000){fault_pose("ARRIVAL_DEADLINE",pose,clock.now_us());return;}
    const int observation=contract->observe(pose,clock.now_us(),sent_);
    if(observation<0){fault_pose("STEP_STATE_CHANGED",pose,clock.now_us());return;}
    const bool arrived=observation==1;
    arrivals_=arrived?arrivals_+1:0;
    publish("SHOULDER_STEP_SAMPLE",pose,arrivals_>=3?P::Complete:P::Observe,clock.now_us(),arrived?1:0);
  }
  // Parent interface for existing fault-settling adapter; original record is retained.
  ShoulderPreloadPhase phase()const{return phase_==CompensatedStepPhase::Fault?ShoulderPreloadPhase::Fault:
    phase_==CompensatedStepPhase::Complete?ShoulderPreloadPhase::Complete:ShoulderPreloadPhase::Observe;}
  CompensatedStepPhase local_phase()const{return phase_;}
  const char* boot_id()const{return boot_;}const char* command_id()const{return command_;}
  const char* reason()const{return reason_;}unsigned writes()const{return writes_;}
  unsigned sequence()const{return sequence_;}const char* record()const{return barrier_.retained();}
  size_t record_size()const{return barrier_.size();}
 private:
  void fail(const char* reason){reason_=reason;phase_=CompensatedStepPhase::Fault;}
  void fault_pose(const char* why,const ShoulderPreloadPose& p,uint64_t now){publish("STATE_MISMATCH",p,CompensatedStepPhase::Fault,now);fail(why);}
  void publish(const char* event,const ShoulderPreloadPose& pose,CompensatedStepPhase next,uint64_t now,int result=0){
    if(!shoulder_event_json(event,pose,0,result,boot_,command_,sequence_,scratch_,sizeof(scratch_))){fail("PUBLICATION_FAILED");return;}
    JsonDocument doc;
    if(deserializeJson(doc,scratch_)){fail("PUBLICATION_FAILED");return;}
    doc["motion_contract"]="rocell.compensated_shoulder_step.v1";
    if(const auto* contract=auth_.contract()){
      doc["model_id"]="r29-frozen-offset-v1";
      auto desired=doc["desired_positions"].to<JsonArray>();
      auto commands=doc["command_goals"].to<JsonArray>();
      auto predicted=doc["predicted_positions"].to<JsonArray>();
      auto error=doc["desired_error_counts"].to<JsonArray>();
      auto residual=doc["goal_residual_counts"].to<JsonArray>();
      for(int i=0;i<2;++i){
        desired.add(contract->desired[i]);commands.add(contract->command_goals[i]);predicted.add(contract->predicted[i]);
        error.add(int(pose.position[i+1])-contract->desired[i]);
        residual.add(int(pose.position[i+1])-int(pose.goal[i+1]));
      }
      doc["arrival_tolerance_counts"]=2;
    }
    if(!hold_json_finish(doc,scratch_,sizeof(scratch_))||
       !barrier_.stage(sequence_,scratch_,strlen(scratch_),now,now+10000000)){fail("PUBLICATION_FAILED");return;}
    next_=next;phase_=CompensatedStepPhase::Waiting;
  }
  CompensatedShoulderAuthorization auth_;ShoulderReceiptVerifier<Crypto> verifier_;
  ShoulderExportBarrier<Crypto,ShoulderReceiptVerifier<Crypto>> barrier_;Crypto& crypto_;
  CompensatedStepPhase phase_=CompensatedStepPhase::Capture,next_=CompensatedStepPhase::Fault;
  char boot_[33]={},command_[101]={},scratch_[4096]={},references_[3][4096]={};
  size_t reference_sizes_[3]={};unsigned captured_=0,sequence_=0,writes_=0,arrivals_=0;
  uint64_t last_finished_=0,sent_=0;const char* reason_="COMPENSATED_STEP_CANDIDATE";
};
}
