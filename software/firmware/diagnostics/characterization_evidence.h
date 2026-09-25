// Bounded RAM evidence for one leg. Reuse only after the owning session confirms
// its signed result-export receipt. RAM retention is not durable host export.
#pragma once
#include "shoulder_characterization_policy.h"
#include <cstring>
namespace rocell_diag {
enum class CampaignEvent {Baseline,Intent,Prewrite,Sent,Observation,Result};
struct CampaignEvidenceRecord {
  CampaignEvent event;ShoulderPreloadPose pose;CharacterizationResult result;
  bool has_result=false;
};
class CharacterizationEvidence {
 public:
  bool operator()(const char* name,unsigned leg,const ShoulderPreloadPose& pose,
                  const CharacterizationResult* result){
    if(failed_)return false;
    if(!name||leg!=leg_||leg>=12||count_==71||sealed_)return fail();
    CampaignEvent event;
    if(!strcmp(name,"BASELINE"))event=CampaignEvent::Baseline;
    else if(!strcmp(name,"INTENT"))event=CampaignEvent::Intent;
    else if(!strcmp(name,"PREWRITE"))event=CampaignEvent::Prewrite;
    else if(!strcmp(name,"SENT_UNACKNOWLEDGED"))event=CampaignEvent::Sent;
    else if(!strcmp(name,"OBSERVATION"))event=CampaignEvent::Observation;
    else if(!strcmp(name,"RESULT"))event=CampaignEvent::Result;
    else return fail();
    // Enforce expected phases, so incomplete evidence cannot be sealed/released.
    bool valid=count_<3?event==CampaignEvent::Baseline:
      count_==3?event==CampaignEvent::Intent:count_==4?event==CampaignEvent::Prewrite:
      count_==5?event==CampaignEvent::Sent:
      event==CampaignEvent::Observation||(event==CampaignEvent::Result&&observations_>=3);
    if(!valid||(event==CampaignEvent::Result)!=(result!=nullptr))return fail();
    if(event==CampaignEvent::Observation&&observations_==64)return fail();
    auto& record=records_[count_++];record.event=event;record.pose=pose;
    record.has_result=result!=nullptr;if(result)record.result=*result;
    if(event==CampaignEvent::Observation)++observations_;
    if(result){sealed_=true;eligible_=result->continuation_eligible();}
    return true;
  }
  // The caller must obtain completed directly from its private session, never
  // from a request body. A failed/unsealed leg is preserved, not reusable.
  bool release_after_receipt(unsigned completed){
    if(failed_||!sealed_||!eligible_||completed!=leg_+1)return fail();
    ++leg_;count_=observations_=0;sealed_=eligible_=false;return true;
  }
  size_t size()const{return count_;}
  const CampaignEvidenceRecord* record(size_t index)const{return index<count_?&records_[index]:nullptr;}
  bool failed()const{return failed_;}
 private:
  bool fail(){failed_=true;return false;}
  CampaignEvidenceRecord records_[71];unsigned leg_=0,count_=0,observations_=0;
  bool failed_=false,sealed_=false,eligible_=false;
};
}
