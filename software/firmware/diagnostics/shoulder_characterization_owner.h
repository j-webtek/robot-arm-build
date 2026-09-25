// Offline owner candidate. No routes or hardware adapter. Evidence/admission
// callbacks are test seams, NOT replacements for authenticated release binding.
#pragma once
#include "shoulder_characterization_policy.h"
#include "characterization_export_barrier.h"
#include <cstring>
namespace rocell_diag {
struct CharacterizationManifest {
  uint16_t goals[12][2]={},bounds[7][2]={};
  unsigned legs=0;uint64_t maximum_us=60000000;
};
enum class CharacterizationPhase { New, Baseline, Prewrite, Observe, AwaitExport, Complete, Fault };
struct CharacterizationFault {
  bool present=false,has_last_valid_pose=false;
  const char* reason="";CharacterizationPhase phase=CharacterizationPhase::New;
  unsigned leg=0,writes=0;uint64_t last_owner_time_us=0;
  ShoulderPreloadPose last_valid_pose;
};
class ShoulderCharacterizationOwner {
 public:
  bool begin(const CharacterizationManifest& manifest,uint64_t now){
    if(phase_!=CharacterizationPhase::New)return false;
    phase_=CharacterizationPhase::Fault;reason_="MANIFEST_REJECTED";
    if(!now||!manifest.legs||manifest.legs>12||!manifest.maximum_us||manifest.maximum_us>60000000)return false;
    for(int i=0;i<7;++i)if(manifest.bounds[i][0]>manifest.bounds[i][1]||manifest.bounds[i][1]>4095)return false;
    for(unsigned n=0;n<manifest.legs;++n){
      if(int(manifest.goals[n][0])+manifest.goals[n][1]!=4114)return false;
      for(int i=0;i<2;++i)if(manifest.goals[n][i]<manifest.bounds[i+1][0]||manifest.goals[n][i]>manifest.bounds[i+1][1])return false;
      if(n&&(!std::abs(int(manifest.goals[n][0])-int(manifest.goals[n-1][0]))||
          std::abs(int(manifest.goals[n][0])-int(manifest.goals[n-1][0]))>24))return false;
    }
    manifest_=manifest;
    ab_=manifest.legs==3&&manifest.goals[0][0]==2377&&manifest.goals[1][0]==2389&&
      (manifest.goals[2][0]==2387||manifest.goals[2][0]==2378);
    forward_repeat_=manifest.legs==4&&manifest.goals[0][0]==2389&&manifest.goals[1][0]==2377&&
      manifest.goals[2][0]==2389&&manifest.goals[3][0]==2378;
    reverse_=manifest.legs==3&&manifest.goals[0][0]==2389&&manifest.goals[1][0]==2377&&
      (manifest.goals[2][0]==2385||manifest.goals[2][0]==2386);
    heldout_=manifest.legs==2&&manifest.goals[0][0]==2377&&
      (manifest.goals[1][0]==2388||manifest.goals[1][0]==2389);
    second_heldout_=((manifest.legs==3&&manifest.goals[0][0]==2377&&
      manifest.goals[1][0]==2389&&manifest.goals[2][0]==2378)||
      (manifest.legs==4&&manifest.goals[0][0]==2389&&manifest.goals[1][0]==2377&&
       manifest.goals[2][0]==2389&&manifest.goals[3][0]==2386));
    // The complete authenticated target list selects this policy. Legacy,
    // matched and arbitrary twelve-leg manifests cannot opt in accidentally.
    const int offsets[12]={-4,0,-8,0,-12,0,-4,0,-8,0,-12,0};
    matrix_=manifest.legs==12;
    for(unsigned n=0;matrix_&&n<12;++n)
      matrix_=int(manifest.goals[n][0])==int(manifest.goals[1][0])+offsets[n]&&
        int(manifest.goals[n][1])==int(manifest.goals[1][1])-offsets[n];
    const int mapping[12]={2377,2389,2379,2387,2381,2389,2377,2385,2389,2383,2377,2388};
    mapping_batch_=manifest.legs==12;
    for(unsigned n=0;mapping_batch_&&n<12;++n)
      mapping_batch_=manifest.goals[n][0]==mapping[n]&&manifest.goals[n][1]==4114-mapping[n];
    const int separated[12]={2389,2377,2385,2389,2383,2377,2388,2377,2381,2389,2377,2387};
    bool separated_mapping=manifest.legs==12;
    for(unsigned n=0;separated_mapping&&n<12;++n)
      separated_mapping=manifest.goals[n][0]==separated[n]&&manifest.goals[n][1]==4114-separated[n];
    mapping_batch_=mapping_batch_||separated_mapping;
    const int fine_lookup[12]={2377,2385,2389,2377,2385,2389,2377,2388,2389,2377,2388,2389};
    bool fine_lookup_validation=manifest.legs==12;
    for(unsigned n=0;fine_lookup_validation&&n<12;++n)
      fine_lookup_validation=manifest.goals[n][0]==fine_lookup[n]&&manifest.goals[n][1]==4114-fine_lookup[n];
    mapping_batch_=mapping_batch_||fine_lookup_validation;
    const int local_interval[11]={2377,2383,2389,2377,2385,2389,2377,2388,2389,2377,2389};
    bool local_interval_campaign=manifest.legs==11;
    for(unsigned n=0;local_interval_campaign&&n<11;++n)
      local_interval_campaign=manifest.goals[n][0]==local_interval[n]&&manifest.goals[n][1]==4114-local_interval[n];
    mapping_batch_=mapping_batch_||local_interval_campaign;
    // Only the complete fixed transition route can select the narrow
    // one-count response policy. A prefix or arbitrary twelve-leg list cannot.
    const int ghost_pair[12]={2377,2386,2388,2386,2388,2386,2377,2386,2388,2386,2388,2389};
    ghost_pair_transition_=manifest.legs==12;
    for(unsigned n=0;ghost_pair_transition_&&n<12;++n)
      ghost_pair_transition_=manifest.goals[n][0]==ghost_pair[n]&&
        manifest.goals[n][1]==4114-ghost_pair[n];
    mapping_batch_=mapping_batch_||ghost_pair_transition_;
    const int visible_interval[4]={2401,2389,2401,2413};
    bool visible_interval_campaign=manifest.legs==4;
    for(unsigned n=0;visible_interval_campaign&&n<4;++n)
      visible_interval_campaign=manifest.goals[n][0]==visible_interval[n]&&
        manifest.goals[n][1]==4114-visible_interval[n];
    mapping_batch_=mapping_batch_||visible_interval_campaign;
    started_=last_clock_=now;phase_=CharacterizationPhase::Baseline;reason_="RUNNING";return true;
  }
  template<class Bus,class Clock,class Evidence,class Admission>
  void advance(Bus& bus,Clock& clock,Evidence& evidence,Admission& admitted){
    using P=CharacterizationPhase;
    if(phase_==P::New||phase_==P::Fault||phase_==P::Complete)return;
    auto now=clock.now_us();
    if(now<last_clock_||now-started_>manifest_.maximum_us){fail("CAMPAIGN_TIME");return;}
    last_clock_=now;
    if(bus.End||!admitted()){fail("ADMISSION_LOST");return;}
    // No bus access while waiting for durable host export. After acceptance the
    // next leg still reacquires three baselines against the retained endpoint.
    if(phase_==P::AwaitExport){
      if(now-export_started_>5000000)fail("EXPORT_DEADLINE");
      return;
    }
    if(last_scan_&&now-last_scan_<100000)return;
    ShoulderPreloadPose pose;
    if(!ShoulderPreloadCandidate::sample(bus,clock,pose,admitted)||!valid_absolute(pose)){
      fail("FEEDBACK_OR_BOUNDS");return;
    }
    last_valid_pose_=pose;has_last_valid_pose_=true;
    if(pose.started_us<=last_scan_){fail("CLOCK_REVERSED");return;}
    if(last_scan_&&pose.started_us-last_scan_>1000000){fail("FEEDBACK_GAP");return;}
    last_scan_=pose.finished_us;
    if(clock.now_us()-started_>manifest_.maximum_us){fail("CAMPAIGN_TIME");return;}
    if(phase_==P::Baseline){
      if(!stationary(pose)){fail("BASELINE_MOVING");return;}
      if(!baseline_count_){
        if(leg_&& !pose_matches(pose,previous_)){fail("PREDECESSOR_CHANGED");return;}
        baseline_=pose;if(!leg_){
          anchor_=pose;anchor_set_=true;
          if(matrix_&&(pose.goal[1]!=manifest_.goals[1][0]||pose.goal[2]!=manifest_.goals[1][1])){
            fail("MATRIX_ANCHOR_CHANGED");return;
          }
          // Freeze total campaign target travel against the first measured pose,
          // not each subsequent target (which would permit cumulative walking).
          for(unsigned n=0;n<manifest_.legs;++n)for(int j=0;j<2;++j)
            if(std::abs(int(manifest_.goals[n][j])-int(anchor_.position[j+1]))>32){
              fail("CAMPAIGN_TARGET_EXCURSION");return;
            }
        }
      }else if(!pose_matches(pose,baseline_)){fail("BASELINE_CHANGED");return;}
      if(!neighbors(pose)||!travel(pose)){fail("BASELINE_ADMISSION");return;}
      if(!evidence("BASELINE",leg_,pose,nullptr)){fail("EXPORT_FAILED");return;}
      if(++baseline_count_==3){
        if(!evidence("INTENT",leg_,pose,nullptr)){fail("EXPORT_FAILED");return;}
        phase_=P::Prewrite;
      }
      return;
    }
    if(phase_==P::Prewrite){
      if(!stationary(pose)||!pose_matches(pose,baseline_)||!neighbors(pose)||!travel(pose)){
        fail("PREWRITE_CHANGED");return;
      }
      if(!evidence("PREWRITE",leg_,pose,nullptr)){fail("EXPORT_FAILED");return;}
      now=clock.now_us();
      if(now<pose.finished_us||now-pose.finished_us>100000||now-started_>manifest_.maximum_us||!admitted()){
        fail("PREWRITE_EXPIRED");return;
      }
      uint8_t ids[2]={12,13},acc[2]={1,1};uint16_t speeds[2]={20,20};
      int16_t targets[2]={int16_t(manifest_.goals[leg_][0]),int16_t(manifest_.goals[leg_][1])};
      ++writes_;bus.SyncWritePosEx(ids,2,targets,speeds,acc);sent_=clock.now_us();
      if(!evidence("SENT_UNACKNOWLEDGED",leg_,pose,nullptr)){fail("EXPORT_FAILED");return;}
      phase_=P::Observe;return;
    }
    if(pose.started_us<=sent_||pose.finished_us-sent_>8000000||samples_count_>=64){fail("LEG_DEADLINE");return;}
    for(int i=0;i<7;++i){
      bool selected=i==1||i==2;int expected=selected?manifest_.goals[leg_][i-1]:baseline_.goal[i];
      int delta=int(pose.position[i])-int(baseline_.position[i]);
      if(pose.goal[i]!=expected){fail("GOAL_READBACK");return;}
      if(selected){
        int command_delta=int(manifest_.goals[leg_][i-1])-int(baseline_.goal[i]);
        if(std::abs(delta)>32||delta*(command_delta>0?1:-1)<-1){fail("DIRECTION_OR_TRAVEL");return;}
      }else if(std::abs(delta)>2||ShoulderCharacterizationPolicy::moving(pose,i)){fail("NEIGHBOR_CHANGED");return;}
    }
    if(!neighbors(pose)){fail("CAMPAIGN_NEIGHBOR_CHANGED");return;}
    samples_[samples_count_++]=pose;
    if(!evidence("OBSERVATION",leg_,pose,nullptr)){fail("EXPORT_FAILED");return;}
    if(samples_count_<3)return;
    auto result=ShoulderCharacterizationPolicy::assess(baseline_,manifest_.goals[leg_],samples_,samples_count_,manifest_.bounds,true,true);
    if(result.outcome==CharacterizationOutcome::Stop&&std::strcmp(result.reason,"NOT_SETTLED")==0)return;
    // Small net response can conceal a transient or a delayed response. Observe
    // for two seconds after the single write; never resend to provoke movement.
    if(result.outcome==CharacterizationOutcome::Stop&&std::strcmp(result.reason,"NO_CLEAR_RESPONSE")==0&&
       pose.finished_us-((matrix_||mapping_batch_)?samples_[0].started_us:sent_)<2000000)return;
    if(ghost_pair_transition_){
      // All legs must land near their frozen encoder endpoint. A direct leg
      // additionally requires at least one count of actual primary travel in
      // the requested direction; goal readback alone cannot pass it. A small
      // reverse step can settle later than the first three scans, so do not
      // classify its endpoint or direction before the full observation window.
      const int primary=manifest_.goals[leg_][0];
      const int expected_primary=primary==2377?2385:primary==2386?2388:
        primary==2388?2390:2391;
      const int expected_pair=primary==2377?1730:primary==2386?1727:
        primary==2388?1725:1724;
      const bool direct=(leg_>=2&&leg_<=5)||(leg_>=8&&leg_<=10);
      if(direct&&result.outcome!=CharacterizationOutcome::Stop&&
         pose.finished_us-samples_[0].started_us<2000000)return;
      const int actual_primary=int(pose.position[1])-int(baseline_.position[1]);
      const int actual_pair=int(pose.position[2])-int(baseline_.position[2]);
      const int commanded=int(manifest_.goals[leg_][0])-int(baseline_.goal[1]);
      if(std::abs(int(pose.position[1])-expected_primary)>2||
         std::abs(int(pose.position[2])-expected_pair)>2||
         (direct&&(actual_primary*(commanded>0?1:-1)<1||
                   actual_pair*(commanded>0?-1:1)<0))){
        fail("GHOST_ENDPOINT_OR_DIRECTION");return;
      }
      if(direct&&result.outcome==CharacterizationOutcome::Stop&&
         std::strcmp(result.reason,"NO_CLEAR_RESPONSE")==0){
        if(direct_small_streak_>=4){fail("GHOST_SMALL_STREAK");return;}
        result.outcome=CharacterizationOutcome::SettledSmall;
        result.reason="GHOST_VERIFIED_SMALL_RESPONSE";
      }
    }
    // Retain small motion as its own outcome, never as accurate arrival.
    // Promotion applies only after the unchanged validator and observation
    // window; the accepted-export counter prevents two consecutive small legs.
    if((matrix_||mapping_batch_)&&result.outcome==CharacterizationOutcome::Stop&&
        std::strcmp(result.reason,"NO_CLEAR_RESPONSE")==0&&consecutive_small_==0&&
        std::abs(result.endpoint_error[0])<=12&&std::abs(result.endpoint_error[1])<=12){
      result.outcome=CharacterizationOutcome::SettledSmall;result.reason="SMALL_RESPONSE_RETAINED";
    }
    if(!evidence("RESULT",leg_,pose,&result)){fail("EXPORT_FAILED");return;}
    if(!result.continuation_eligible()){
      pending_result_=result;encode_result();fail(result.reason);return;
    }
    previous_=pose;pending_result_=result;encode_result();
    export_started_=clock.now_us();export_staged_=false;
    phase_=P::AwaitExport;reason_="AWAITING_RESULT_EXPORT";
  }
  // Hash only our retained bytes, never bytes supplied by the receipt request.
  template<class Crypto>
  bool stage_export(CharacterizationExportBarrier<Crypto>& barrier,uint64_t now){
    if(phase_!=CharacterizationPhase::AwaitExport||export_staged_||!export_time(now)||
        !barrier.stage(leg_,result_bytes_,result_size_,now)){
      fail("EXPORT_STAGE_REJECTED");return false;
    }
    export_staged_=true;last_clock_=now;return true;
  }
  template<class Crypto>
  bool accept_export(CharacterizationExportBarrier<Crypto>& barrier,
      const ShoulderReceiptView& receipt,uint64_t now){
    if(phase_!=CharacterizationPhase::AwaitExport||!export_staged_||!export_time(now)||
        !barrier.accept(receipt,now)||barrier.completed()!=leg_+1){
      fail("EXPORT_RECEIPT_REJECTED");return false;
    }
    if(pending_result_.outcome==CharacterizationOutcome::SettledMiss)++misses_;
    consecutive_small_=pending_result_.outcome==CharacterizationOutcome::SettledSmall?consecutive_small_+1:0;
    if(ghost_pair_transition_){
      const bool direct=(leg_>=2&&leg_<=5)||(leg_>=8&&leg_<=10);
      direct_small_streak_=direct&&pending_result_.outcome==CharacterizationOutcome::SettledSmall?
        direct_small_streak_+1:0;
    }
    ++leg_;baseline_count_=samples_count_=0;last_clock_=now;result_size_=0;
    // Export wait is not a feedback gap. Reacquisition validates the predecessor.
    last_scan_=0;
    if(leg_==manifest_.legs){phase_=CharacterizationPhase::Complete;reason_="MEASUREMENTS_COMPLETE";}
    else {phase_=CharacterizationPhase::Baseline;reason_="RUNNING";}
    return true;
  }
  const uint8_t* result_bytes()const{return result_bytes_;}
  size_t result_size()const{return result_size_;}
  CharacterizationPhase phase()const{return phase_;}
  unsigned writes()const{return writes_;}unsigned completed()const{return leg_;}unsigned misses()const{return misses_;}
  const char* reason()const{return reason_;}
  const CharacterizationFault& fault()const{return fault_;}
 private:
  bool export_time(uint64_t now)const{
    return now>=last_clock_&&now>=export_started_&&now-export_started_<=5000000&&
      now>=started_&&now-started_<=manifest_.maximum_us;
  }
  // Canonical binary v1, big-endian fixed-width fields (no struct padding).
  // Includes manifest, raw baselines/observations and outcome; receipt framing
  // independently binds these exact bytes to boot, campaign and leg sequence.
  void encode_result(){
    result_size_=0;
    auto put=[&](uint64_t value,unsigned width){
      for(int n=int(width)-1;n>=0;--n)result_bytes_[result_size_++]=uint8_t(value>>(n*8));
    };
    const char domain[]="RCCRESULT01";
    for(char c:domain)put(uint8_t(c),1);
    put(leg_,1);put(manifest_.legs,1);put(manifest_.maximum_us,8);
    for(unsigned n=0;n<manifest_.legs;++n)for(auto goal:manifest_.goals[n])put(goal,2);
    for(auto& bound:manifest_.bounds)for(auto value:bound)put(value,2);
    put(pending_result_.outcome==CharacterizationOutcome::SettledSmall?4:
        pending_result_.outcome==CharacterizationOutcome::Stop?3:
        pending_result_.outcome==CharacterizationOutcome::SettledAccurate?1:2,1);
    put(samples_count_,1);
    auto pose=[&](const ShoulderPreloadPose& p){
      put(p.started_us,8);put(p.finished_us,8);
      for(int i=0;i<7;++i){put(p.position[i],2);put(p.goal[i],2);put(p.torque[i],1);
        for(auto byte:p.feedback[i])put(byte,1);}
    };
    pose(baseline_);for(unsigned i=0;i<samples_count_;++i)pose(samples_[i]);
  }
  void fail(const char* reason){
    // Preserve the first cause even if a client retries an invalid receipt.
    if(fault_.present)return;
    fault_.present=true;fault_.reason=reason;fault_.phase=phase_;
    fault_.leg=leg_;fault_.writes=writes_;fault_.last_owner_time_us=last_clock_;
    fault_.has_last_valid_pose=has_last_valid_pose_;
    if(has_last_valid_pose_)fault_.last_valid_pose=last_valid_pose_;
    reason_=reason;phase_=CharacterizationPhase::Fault;
  }
  static bool stationary(const ShoulderPreloadPose& p){for(int i=0;i<7;++i)if(ShoulderCharacterizationPolicy::moving(p,i))return false;return true;}
  static bool pose_matches(const ShoulderPreloadPose& a,const ShoulderPreloadPose& b){
    for(int i=0;i<7;++i)if(a.goal[i]!=b.goal[i]||std::abs(int(a.position[i])-int(b.position[i]))>1)return false;return true;
  }
  bool valid_absolute(const ShoulderPreloadPose& p)const{
    if(!ShoulderCharacterizationPolicy::valid(p))return false;
    for(int i=0;i<7;++i)if(p.position[i]<manifest_.bounds[i][0]||p.position[i]>manifest_.bounds[i][1])return false;
    if(anchor_set_)for(int i=0;i<7;++i)
      if(std::abs(int(p.position[i])-int(anchor_.position[i]))>(i==1||i==2?32:2))return false;
    return true;
  }
  bool neighbors(const ShoulderPreloadPose& p)const{
    for(int i=0;i<7;++i)if(i!=1&&i!=2&&(p.goal[i]!=anchor_.goal[i]||std::abs(int(p.position[i])-int(anchor_.position[i]))>2))return false;
    return true;
  }
  bool travel(const ShoulderPreloadPose& p)const{
    // Enforce matched trial admission natively as well as before host receipt.
    if(ab_&&leg_==2&&(p.goal[1]!=2389||p.goal[2]!=1725||
        std::abs(int(p.position[1])-2391)>1||std::abs(int(p.position[2])-1724)>1))return false;
    if(forward_repeat_&&leg_==3&&(p.goal[1]!=2389||p.goal[2]!=1725||
        std::abs(int(p.position[1])-2391)>1||std::abs(int(p.position[2])-1724)>1))return false;
    if(reverse_&&leg_==2&&(p.goal[1]!=2377||p.goal[2]!=1737||
        std::abs(int(p.position[1])-2385)>1||std::abs(int(p.position[2])-1731)>1))return false;
    if(heldout_&&leg_==1&&(p.goal[1]!=2377||p.goal[2]!=1737||
        std::abs(int(p.position[1])-2385)>1||std::abs(int(p.position[2])-1731)>1))return false;
    if(second_heldout_&&leg_==manifest_.legs-1&&
       (p.goal[1]!=2389||p.goal[2]!=1725||
        std::abs(int(p.position[1])-2391)>1||std::abs(int(p.position[2])-1724)>1))return false;
    int a=int(manifest_.goals[leg_][0])-int(p.goal[1]),b=int(manifest_.goals[leg_][1])-int(p.goal[2]);
    return a&&a==-b&&std::abs(a)<=24&&std::abs(int(manifest_.goals[leg_][0])-int(p.position[1]))<=32&&
      std::abs(int(manifest_.goals[leg_][1])-int(p.position[2]))<=32;
  }
  CharacterizationManifest manifest_;ShoulderPreloadPose anchor_,baseline_,previous_,samples_[64];
  CharacterizationPhase phase_=CharacterizationPhase::New;
  unsigned leg_=0,writes_=0,misses_=0,baseline_count_=0,samples_count_=0;
  uint64_t started_=0,last_clock_=0,last_scan_=0,sent_=0;const char* reason_="NEW";
  CharacterizationResult pending_result_;
  // Header is under 128 bytes; 65 * 156-byte poses fit below 11 KiB.
  uint8_t result_bytes_[11000]={};size_t result_size_=0;
  uint64_t export_started_=0;bool export_staged_=false;
  CharacterizationFault fault_;ShoulderPreloadPose last_valid_pose_;
  bool has_last_valid_pose_=false,anchor_set_=false;
  bool matrix_=false,mapping_batch_=false,ghost_pair_transition_=false;
  unsigned consecutive_small_=0,direct_small_streak_=0;
  bool ab_=false,forward_repeat_=false,reverse_=false,heldout_=false,second_heldout_=false;
};
}
