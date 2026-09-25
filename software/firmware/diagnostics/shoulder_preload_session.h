// Uninstalled resumable owner. Preload-only by default; optional pair hold is a
// separate reviewed scope. No lift. Caller supplies admission and verified receipts.
#pragma once
#include "shoulder_hold_event_json.h"
#include "shoulder_export_barrier.h"
namespace rocell_diag {
enum class ShoulderPreloadPhase { Baseline, Intent, Write, Verify, EnableIntent, Enable,
                                 VerifyEnable, Observe, Waiting, Complete, Fault };
enum class ShoulderSessionScope { PreloadOnly, PairHold, MixedTarget, PosePreparation, ShoulderRise, ClearanceRecovery, StableClearanceRecovery };
template<class Digest,class Verifier> class ShoulderPreloadSession {
 public:
  ShoulderPreloadSession(Digest& digest,Verifier& verifier,const char* boot,const char* command,
      ShoulderSessionScope scope=ShoulderSessionScope::PreloadOnly)
      :barrier_(digest,verifier),scope_(scope){
    if(!valid_identity(boot)||!valid_identity(command)){fail("INVALID_IDENTITY");return;}
    strcpy(boot_,boot);strcpy(command_,command);
  }
  template<class Receipt> bool receipt(const Receipt& value,uint64_t now){
    if(target_deadline_required()&&mixed_sent_&&
       (now<mixed_sent_||now-mixed_sent_>2000000)){fail("MIXED_RECEIPT_DEADLINE");return false;}
    if(enable_time_&&(now<last_scan_||now-last_scan_>500000||now-enable_time_>3000000)){
      fail("HOLD_RECEIPT_GAP");return false;
    }
    if(phase_!=ShoulderPreloadPhase::Waiting||!barrier_.accept(value,now)||!barrier_.consume()){
      fail("EXPORT_RECEIPT_FAILED");return false;
    }
    ++sequence_;phase_=next_;
    // Only a verified, exported three-sample block can open the next joint.
    if(scope_==ShoulderSessionScope::PosePreparation&&phase_==ShoulderPreloadPhase::Baseline){
      mixed_sent_=0;mixed_torque_=-1;observations_=0;
    }
    return true;
  }
  template<class Bus,class Clock,class Admission>
  void advance(Bus& bus,Clock& clock,Admission& admitted){
    using P=ShoulderPreloadPhase;
    if(phase_==P::Complete||phase_==P::Fault)return;
    if(bus.End!=0||!admitted()){fail("ADMISSION_LOST");return;}
    const auto now=clock.now_us();
    if(target_deadline_required()&&mixed_sent_&&
       (now<mixed_sent_||now-mixed_sent_>2000000)){fail("MIXED_OBSERVATION_DEADLINE");return;}
    if(enable_time_&&(now<last_scan_||now-last_scan_>500000||now-enable_time_>3000000)){
      fail("HOLD_OBSERVATION_GAP");return;
    }
    if((scope_==ShoulderSessionScope::ShoulderRise||scope_==ShoulderSessionScope::ClearanceRecovery||scope_==ShoulderSessionScope::StableClearanceRecovery)&&rise_sent_&&
        !(phase_==P::Waiting&&next_==P::Complete)&&
        (now<rise_sent_||now-rise_sent_>5000000)){
      fail("RISE_OBSERVATION_DEADLINE");return;
    }
    if(phase_==P::Waiting){
      barrier_.poll(clock.now_us());
      if(barrier_.state()==ShoulderExportState::Fault)fail("EXPORT_TIMEOUT");
      return; // No read/write progression while waiting for the host.
    }
    if(phase_==P::Observe&&now-last_scan_<100000)return;
    if(scope_==ShoulderSessionScope::StableClearanceRecovery&&phase_==P::Baseline&&baseline_samples_&&now-last_scan_<100000)return;
    ShoulderPreloadPose current;
    if(!ShoulderPreloadCandidate::sample(bus,clock,current,admitted)){fail("FEEDBACK_INVALID");return;}
    if(scope_==ShoulderSessionScope::ShoulderRise||scope_==ShoulderSessionScope::ClearanceRecovery||scope_==ShoulderSessionScope::StableClearanceRecovery){advance_rise(bus,clock,current);return;}
    if(is_target_session()){advance_mixed(bus,clock,current);return;}
    if(phase_==P::Baseline){
      if(current.torque[1]||current.torque[2]){
        fault_state("SHOULDERS_NOT_PASSIVE",current,clock.now_us());return;
      }
      for(int i=0;i<7;++i)if(current.torque[i]&&std::abs(int(current.position[i])-int(current.goal[i]))>2){
        fault_state("ENABLED_JOINT_NOT_TRACKING",current,clock.now_us());return;
      }
      baseline_=current;publish("BASELINE",current,0,0,P::Intent,clock.now_us());return;
    }
    if(phase_==P::EnableIntent||phase_==P::Enable){
      if(!ShoulderPreloadCandidate::consistent(baseline_,current,2)){
        fault_state("PRE_ENABLE_STATE_CHANGED",current,clock.now_us());return;
      }
      if(phase_==P::EnableIntent){publish("PAIR_ENABLE_INTENT",current,0,0,P::Enable,clock.now_us());return;}
      delivery_=enable_.emit_once(bus);enable_time_=clock.now_us();last_scan_=enable_time_;
      publish("PAIR_ENABLE_SENT_UNACKNOWLEDGED",current,0,0,P::VerifyEnable,clock.now_us());return;
    }
    if(phase_==P::VerifyEnable||phase_==P::Observe){
      auto expected=baseline_;expected.torque[1]=expected.torque[2]=1;
      bool matches=ShoulderPreloadCandidate::consistent(expected,current,2);
      for(int i=0;i<7;++i)if(current.feedback[i][2]||current.feedback[i][3]||current.feedback[i][10])matches=false;
      last_scan_=current.finished_us;
      if(phase_==P::Observe)++observations_;
      const bool done=matches&&observations_>=5&&last_scan_-enable_time_>=2000000;
      publish(phase_==P::VerifyEnable?"PAIR_ENABLE_READBACK":"TIMED_HOLD_SAMPLE",current,0,
              matches?1:0,done?P::Complete:P::Observe,clock.now_us());
      if(!matches)fail("HOLD_STATE_CHANGED");
      return;
    }
    const int completed=phase_==P::Verify?index_:index_-1;
    if(!ShoulderPreloadCandidate::consistent(baseline_,current,completed)){
      fault_state("STATE_CHANGED",current,clock.now_us());return;
    }
    current.requested_target=baseline_.position[index_];
    if(phase_==P::Intent){
      publish("PRELOAD_INTENT",current,index_+11,0,P::Write,clock.now_us());return;
    }
    if(phase_==P::Write){
      // This fresh scan follows receipt verification. Never reuse intent-state
      // measurements acquired before an arbitrarily slow host export.
      current.action_started_us=clock.now_us();++writes_;
      const int result=bus.WritePosEx(index_+11,baseline_.position[index_],20,1);
      current.action_device_error=bus.Error;current.action_finished_us=clock.now_us();
      publish("PRELOAD_RESULT",current,index_+11,result,P::Verify,clock.now_us());
      if(result!=1||current.action_device_error!=0)fail("DELIVERY_UNCERTAIN");
      return;
    }
    const int sid=index_+11;
    const auto next=index_==2?(scope_==ShoulderSessionScope::PairHold?P::EnableIntent:P::Complete):P::Intent;
    publish("PRELOAD_VERIFIED",current,sid,1,next,clock.now_us());
    if(index_==1)++index_;
  }
  ShoulderPreloadPhase phase()const{return phase_;}
  const char* reason()const{return reason_;}
  const char* boot_id()const{return boot_;}
  const char* command_id()const{return command_;}
  const char* record()const{return barrier_.retained();}
  size_t record_size()const{return barrier_.size();}
  unsigned sequence()const{return sequence_;}
  unsigned writes()const{return writes_;}
  ShoulderEnableDelivery enable_delivery()const{return delivery_;}
 private:
  bool target_deadline_required()const{
    // Three acquired samples must meet the observation deadline. Once all three
    // are retained, only the export barrier deadline governs their receipt.
    return is_target_session()&&!(scope_==ShoulderSessionScope::PosePreparation&&
        observations_==3&&phase_==ShoulderPreloadPhase::Waiting);
  }
  bool is_target_session()const{return scope_==ShoulderSessionScope::MixedTarget||
    scope_==ShoulderSessionScope::PosePreparation;}
  static int passive_auxiliary(const ShoulderPreloadPose& pose){
    // Never use this scope to initialize either shoulder or the elbow.
    for(int i: {0,4,5,6})if(!pose.torque[i])return i;
    return -1;
  }
  static bool mixed_still(const ShoulderPreloadPose& pose){
    for(int i=0;i<7;++i)if(pose.feedback[i][2]||pose.feedback[i][3]||pose.feedback[i][10])return false;
    return true;
  }
  template<class Bus,class Clock>
  void advance_rise(Bus& bus,Clock& clock,ShoulderPreloadPose& pose){
    using P=ShoulderPreloadPhase;
    const bool stable=scope_==ShoulderSessionScope::StableClearanceRecovery;
    const bool recovery=stable||scope_==ShoulderSessionScope::ClearanceRecovery;
    if(phase_==P::Baseline){
      // One local recovery step only, not a general home or arbitrary target API.
      if(!mixed_still(pose)||pose.position[1]<2439||pose.position[1]>2471||
          pose.position[2]<1643||pose.position[2]>1675||pose.position[3]<2890||pose.position[3]>2922){
        fault_state("RISE_BASELINE_OUTSIDE_REVIEWED_WINDOW",pose,clock.now_us());return;
      }
      if(recovery){
        // One reviewed residual state, not a general relaxation of tracking.
        const int positions[7]={2047,2448,1667,2905,1589,2040,2047};
        const int goals[7]={2047,2443,1671,2907,1589,2040,2047};
        for(int i=0;i<7;++i)if(pose.goal[i]!=goals[i]||std::abs(int(pose.position[i])-positions[i])>2){
          fault_state("RECOVERY_BASELINE_CHANGED",pose,clock.now_us());return;
        }
        const int errors[2]={int(pose.position[1])-int(pose.goal[1]),int(pose.goal[2])-int(pose.position[2])};
        for(int error:errors)if(error<2||error>7){fault_state("RECOVERY_RESIDUAL_CHANGED",pose,clock.now_us());return;}
      }
      for(int i=0;i<7;++i)if(pose.torque[i]!=1||
          (!(recovery&&(i==1||i==2))&&std::abs(int(pose.position[i])-int(pose.goal[i]))>(stable?5:2))){
        fault_state("RISE_BASELINE_NOT_HELD",pose,clock.now_us());return;
      }
      if(stable){
        // Observe, never correct, an existing offset. Require three separately
        // exported stationary scans before any intent or target write.
        if(baseline_samples_){
          for(int i=0;i<7;++i)if(std::abs(int(pose.position[i])-int(baseline_.position[i]))>1||pose.goal[i]!=baseline_.goal[i]){
            fault_state("RECOVERY_BASELINE_UNSTABLE",pose,clock.now_us());return;
          }
          if(pose.started_us<last_scan_||pose.started_us-last_scan_<100000){
            fault_state("RECOVERY_BASELINE_TIMING",pose,clock.now_us());return;
          }
        }else baseline_=pose;
        last_scan_=pose.finished_us;++baseline_samples_;
        publish(baseline_samples_==1?"BASELINE":"BASELINE_STABILITY",pose,0,0,
                baseline_samples_==3?P::Intent:P::Baseline,clock.now_us());return;
      }
      baseline_=pose;publish("BASELINE",pose,0,0,P::Intent,clock.now_us());return;
    }
    const bool after=phase_==P::Verify||phase_==P::Observe;
    bool arrived=true;
    for(int i=0;i<7;++i){
      const bool selected=i==1||i==2;
      const int goal=after&&selected?rise_targets_[i-1]:baseline_.goal[i];
      const int start=baseline_.position[i],value=pose.position[i];
      const int low=after&&i==1?rise_targets_[0]:start;
      const int high=after&&i==2?rise_targets_[1]:start;
      if(pose.torque[i]!=1||pose.goal[i]!=goal||value<low-2||value>high+2||
          ((!after||!selected)&&!stable&&!(recovery&&selected)&&std::abs(value-goal)>2)||
          ((!after||!selected)&&(pose.feedback[i][2]||pose.feedback[i][3]||pose.feedback[i][10]))){
        fault_state("RISE_STATE_CHANGED",pose,clock.now_us());return;
      }
      if(((!stable||selected)&&std::abs(value-goal)>2)||pose.feedback[i][2]||pose.feedback[i][3]||pose.feedback[i][10])arrived=false;
    }
    if(phase_==P::Intent){
      rise_targets_[0]=recovery?baseline_.goal[1]-24:pose.position[1]-12;
      rise_targets_[1]=recovery?baseline_.goal[2]+24:pose.position[2]+12;
      if(recovery&&(pose.position[1]<=rise_targets_[0]||rise_targets_[1]<=pose.position[2]||
          pose.position[1]-rise_targets_[0]>32||rise_targets_[1]-pose.position[2]>32)){
        fault_state("RECOVERY_TRAVEL_BOUND",pose,clock.now_us());return;
      }
      for(int i=0;i<2;++i)rise_start_[i]=pose.position[i+1];
      for(int i=0;i<2;++i)pose.requested_pair[i]=rise_targets_[i];
      publish("SHOULDER_STEP_INTENT",pose,0,0,P::Write,clock.now_us());return;
    }
    for(int i=0;i<2;++i)pose.requested_pair[i]=rise_targets_[i];
    if(phase_==P::Write){
      if(pose.position[1]!=rise_start_[0]||pose.position[2]!=rise_start_[1]){
        fault_state("RISE_PREWRITE_POSITION_CHANGED",pose,clock.now_us());return;
      }
      uint8_t ids[2]={12,13},acc[2]={1,1};uint16_t speed[2]={20,20};
      int16_t targets[2]={int16_t(rise_targets_[0]),int16_t(rise_targets_[1])};
      pose.action_started_us=clock.now_us();++writes_;
      // Broadcast target packet has no servo acknowledgement. Goal and position
      // readbacks, not this send, must establish the result. Never retry it.
      bus.SyncWritePosEx(ids,2,targets,speed,acc);
      rise_sent_=pose.action_finished_us=clock.now_us();
      publish("SHOULDER_STEP_SENT",pose,0,0,P::Verify,clock.now_us());return;
    }
    if(!after||pose.started_us<=rise_sent_||pose.finished_us-rise_sent_>5000000){
      fault_state("RISE_SCAN_ORDER",pose,clock.now_us());return;
    }
    last_scan_=pose.finished_us;observations_=arrived?observations_+1:0;
    const bool complete=observations_>=3;
    reason_=complete?"SHOULDER_RISE_OBSERVED":"OBSERVING_SHOULDER_RISE";
    publish("SHOULDER_STEP_SAMPLE",pose,0,arrived?1:0,complete?P::Complete:P::Observe,clock.now_us());
  }
  bool mixed_matches(const ShoulderPreloadPose& pose,bool after){
    if(!mixed_still(pose))return false;
    for(int i=0;i<7;++i){
      if(std::abs(int(pose.position[i])-int(baseline_.position[i]))>2)return false;
      if(after&&i==index_){
        if(pose.goal[i]!=mixed_target_||
            (scope_==ShoulderSessionScope::PosePreparation&&pose.torque[i]&&
             std::abs(int(pose.position[i])-int(pose.goal[i]))>2))return false;
      }
      else if(pose.goal[i]!=baseline_.goal[i]||pose.torque[i]!=baseline_.torque[i])return false;
      if(i!=index_&&pose.torque[i]&&std::abs(int(pose.position[i])-int(pose.goal[i]))>2)return false;
    }
    return true;
  }
  template<class Bus,class Clock>
  void advance_mixed(Bus& bus,Clock& clock,ShoulderPreloadPose& pose){
    using P=ShoulderPreloadPhase;
    if(phase_==P::Baseline){
      const bool preparing=scope_==ShoulderSessionScope::PosePreparation;
      if(!mixed_still(pose)||(!preparing&&pose.torque[1]+pose.torque[2]!=1)||
          (preparing&&(!pose.torque[1]||!pose.torque[2]||!pose.torque[3]||passive_auxiliary(pose)<0))){
        fault_state("MIXED_BASELINE_INVALID",pose,clock.now_us());return;
      }
      if(preparing&&writes_){
        for(int i=0;i<7;++i)if(pose.goal[i]!=baseline_.goal[i]||pose.torque[i]!=baseline_.torque[i]||
            std::abs(int(pose.position[i])-int(initial_position_[i]))>2){
          fault_state("PREPARATION_CONTINUITY_LOST",pose,clock.now_us());return;
        }
      }
      for(int i=0;i<7;++i)if(pose.torque[i]&&std::abs(int(pose.position[i])-int(pose.goal[i]))>2){
        fault_state("ENABLED_JOINT_NOT_TRACKING",pose,clock.now_us());return;
      }
      if(preparing&&!writes_)for(int i=0;i<7;++i)initial_position_[i]=pose.position[i];
      baseline_=pose;index_=preparing?passive_auxiliary(pose):(pose.torque[1]?2:1);
      publish("BASELINE",pose,0,0,P::Intent,clock.now_us());return;
    }
    if(phase_==P::Intent||phase_==P::Write){
      if(!mixed_matches(pose,false)||(phase_==P::Write&&pose.position[index_]!=mixed_target_)){
        fault_state("MIXED_PREWRITE_CHANGED",pose,clock.now_us());return;
      }
      if(phase_==P::Intent){
        mixed_target_=pose.position[index_];pose.requested_target=mixed_target_;
        publish("PRELOAD_INTENT",pose,index_+11,0,P::Write,clock.now_us());return;
      }
      pose.requested_target=mixed_target_;pose.action_started_us=clock.now_us();++writes_;
      int result=bus.WritePosEx(index_+11,mixed_target_,20,1);
      pose.action_device_error=bus.Error;pose.action_finished_us=clock.now_us();mixed_sent_=pose.action_finished_us;
      publish("PRELOAD_RESULT",pose,index_+11,result,P::Verify,clock.now_us());
      if(result!=1||pose.action_device_error)fail("DELIVERY_UNCERTAIN");return;
    }
    if(phase_!=P::Verify){fault_state("MIXED_PHASE_INVALID",pose,clock.now_us());return;}
    if(pose.started_us<=mixed_sent_||pose.finished_us-mixed_sent_>2000000||!mixed_matches(pose,true)||
        (mixed_torque_!=-1&&mixed_torque_!=pose.torque[index_])){
      fault_state("MIXED_POSTWRITE_CHANGED",pose,clock.now_us());return;
    }
    mixed_torque_=pose.torque[index_];++observations_;
    reason_=mixed_torque_?"TARGET_OBSERVED_ENABLED":"TARGET_OBSERVED_PASSIVE";
    auto next=observations_==3?P::Complete:P::Verify;
    if(scope_==ShoulderSessionScope::PosePreparation){
      for(int i=0;i<7;++i)if(std::abs(int(pose.position[i])-int(initial_position_[i]))>2){
        fault_state("PREPARATION_POSE_CHANGED",pose,clock.now_us());return;
      }
      if(observations_==3){
        if(mixed_torque_!=1){fault_state("TARGET_REMAINED_PASSIVE",pose,clock.now_us());return;}
        if(passive_auxiliary(pose)>=0)next=P::Baseline;
        else reason_="POSE_PREPARATION_OBSERVED";
        baseline_=pose;
      }
    }
    publish("PRELOAD_VERIFIED",pose,index_+11,1,next,clock.now_us());
  }
  void fault_state(const char* reason,const ShoulderPreloadPose& current,uint64_t now){
    // Preserve the already-acquired failing scan. No additional bus reads or
    // rollback; without this record the host cannot identify the failing joint.
    publish("STATE_MISMATCH",current,0,0,ShoulderPreloadPhase::Fault,now);
    fail(reason);
  }
  void fail(const char* reason){reason_=reason;phase_=ShoulderPreloadPhase::Fault;}
  void publish(const char* event,const ShoulderPreloadPose& pose,int sid,int result,
               ShoulderPreloadPhase next,uint64_t now){
    if(!shoulder_event_json(event,pose,sid,result,boot_,command_,sequence_,scratch_,sizeof(scratch_))||
       !barrier_.stage(sequence_,scratch_,strlen(scratch_),now,now+10000000)){
      fail("RECORD_PUBLICATION_FAILED");return;
    }
    next_=next;phase_=ShoulderPreloadPhase::Waiting;
  }
  ShoulderExportBarrier<Digest,Verifier> barrier_;ShoulderPreloadPose baseline_;
  ShoulderSessionScope scope_;ShoulderEnablePacketCandidate enable_;
  ShoulderEnableDelivery delivery_=ShoulderEnableDelivery::NotAttempted;
  uint64_t enable_time_=0,last_scan_=0;unsigned observations_=0;
  ShoulderPreloadPhase phase_=ShoulderPreloadPhase::Baseline,next_=ShoulderPreloadPhase::Fault;
  int index_=1;unsigned sequence_=0,writes_=0;const char* reason_="RESUMABLE_PRELOAD";
  uint64_t mixed_sent_=0;uint16_t mixed_target_=0;int mixed_torque_=-1;
  uint16_t initial_position_[7]={};
  unsigned baseline_samples_=0;
  uint64_t rise_sent_=0;uint16_t rise_targets_[2]={},rise_start_[2]={};
  char boot_[129]={},command_[129]={},scratch_[4096]={};
};
}
