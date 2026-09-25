#include "characterization_evidence.h"
#include <cassert>
#include <memory>
int main(){
 using Store=rocell_diag::CharacterizationEvidence;
 rocell_diag::ShoulderPreloadPose pose;
 rocell_diag::CharacterizationResult result;result.outcome=rocell_diag::CharacterizationOutcome::SettledMiss;
 auto store=std::make_unique<Store>();
 for(unsigned leg=0;leg<12;++leg){
   for(int i=0;i<3;++i)assert((*store)("BASELINE",leg,pose,nullptr));
   for(auto event:{"INTENT","PREWRITE","SENT_UNACKNOWLEDGED"})assert((*store)(event,leg,pose,nullptr));
   for(int i=0;i<64;++i)assert((*store)("OBSERVATION",leg,pose,nullptr));
   assert((*store)("RESULT",leg,pose,&result)&&store->size()==71);
   assert(store->record(70)->has_result&&!store->record(71));
   assert(store->release_after_receipt(leg+1)&&store->size()==0);
 }
 assert(!(*store)("BASELINE",12,pose,nullptr));
 store=std::make_unique<Store>();assert(!store->release_after_receipt(1));
 assert(!(*store)("BASELINE",0,pose,nullptr));
 store=std::make_unique<Store>();assert(!(*store)("OBSERVATION",0,pose,nullptr));
 store=std::make_unique<Store>();assert(!(*store)("BASELINE",1,pose,nullptr));
}
