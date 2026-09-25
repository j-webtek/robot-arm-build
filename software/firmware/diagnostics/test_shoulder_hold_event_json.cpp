#define main preload_cases
#include "test_shoulder_preload_candidate.cpp"
#undef main
#include "shoulder_hold_event_json.h"
#include <vector>
struct Sink {
 std::vector<std::string> records;bool fail=false;
 bool persist(unsigned sequence,const char* bytes,size_t length){
   assert(sequence==records.size());if(fail)return false;
   records.emplace_back(bytes,length);return true;
 }
};
int main(){
 Sink sink;rocell_diag::ShoulderHoldEvidenceSink<Sink> evidence(sink,"abababababababababababababababab","shoulder-test-1");
 Bus bus;Clock clock;rocell_diag::ShoulderPreloadCandidate owner;auto gate=[](){return true;};
 assert(owner.run(bus,clock,evidence,gate));assert(sink.records.size()==7);
 for(const auto& raw:sink.records){
   JsonDocument doc;assert(!deserializeJson(doc,raw));
   assert(doc["joints"].size()==7);
   if(doc["event"]=="PRELOAD_RESULT"){
     assert(doc["snapshot_role"]=="PRE_ACTION");assert(doc["device_error"]==0);
     assert(doc["action_finished_us"].as<uint64_t>()>=doc["action_started_us"].as<uint64_t>());
   }
   std::cout<<raw<<"\n";
 }
 Sink failed;failed.fail=true;
 rocell_diag::ShoulderHoldEvidenceSink<Sink> rejected(failed,"abababababababababababababababab","shoulder-test-2");
 Bus untouched;Clock clock2;rocell_diag::ShoulderPreloadCandidate blocked;
 assert(!blocked.run(untouched,clock2,rejected,gate)&&untouched.writes==0);
 rocell_diag::ShoulderHoldCandidate not_run;char terminal[1024];
 assert(rocell_diag::shoulder_hold_terminal_json(not_run,"abababababababababababababababab","not-run",0,terminal,sizeof(terminal)));
 JsonDocument doc;assert(!deserializeJson(doc,terminal));
 assert(!doc["timed_observation_complete"].as<bool>()&&!doc["lift_authorized"].as<bool>());
 assert(doc["enable_delivery"]=="NOT_ATTEMPTED");
}
