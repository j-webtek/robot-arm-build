// Reuse scripted bus/controller cases; no Arduino or physical device.
#define main run_owner_cases
#include "test_hold_initialization_owner.cpp"
#undef main
#include <iostream>
#include <string>
#include <vector>
#include "hold_evidence_publisher.h"
#include "evidence_store.h"
struct Sink {
  int fail_at=-1;bool failed=false,reserved=false;
  std::vector<std::string> records;
  bool reserve(size_t count){assert(count==11);reserved=true;return true;}
  bool faulted()const{return failed;}
  bool publish(const char*,const char* record){
    assert(reserved&&records.size()<11&&strlen(record)<4096);
    if(int(records.size())==fail_at){failed=true;return false;}
    records.emplace_back(record);return true;
  }
};
int main(int argc,char** argv){
  if(argc==2&&(std::strcmp(argv[1],"--fast-powered")==0||
               std::strcmp(argv[1],"--fast-busy")==0)){
    // Model a transient servo busy flag independently of the owner's polling.
    struct TimedBus:Bus {
      Clock& clock;bool persistent;uint64_t written=0;
      TimedBus(Clock& c,bool p):clock(c),persistent(p){}
      int WritePosEx(uint8_t id,int16_t target,uint16_t speed,uint8_t acc){
        written=clock.tick;return Bus::WritePosEx(id,target,speed,acc);
      }
      int Read(uint8_t id,uint8_t address,uint8_t* out,uint8_t width){
        elbow_moving=writes&&(persistent||clock.tick-written<100000);
        return Bus::Read(id,address,out,width);
      }
    };
    Clock clock;const bool persistent=std::strcmp(argv[1],"--fast-busy")==0;
    TimedBus bus(clock,persistent);bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2724;
    HoldInitializationOwner owner(policy(true));HoldEvidencePublisher publisher;Sink sink;
    assert(publisher.begin(sink,"test-boot","test-hold"));
    for(int i=0;i<100;++i){clock.tick+=10000;publisher.poll(owner,bus,clock,sink);}
    assert(owner.phase()==(persistent?HoldPhase::Fault:HoldPhase::Captured));
    assert(bus.writes==1&&bus.enables==0);
    assert(owner.scan(3)->started_us()>=owner.action(0)->finished_us+100000);
    const int reads=bus.reads;
    publisher.poll(owner,bus,clock,sink);
    assert(bus.reads==reads&&bus.writes==1&&bus.enables==0);
    for(const auto& record:sink.records)std::cout<<record<<"\n";
    return 0;
  }
  if(argc==2&&std::strcmp(argv[1],"--already-enabled")==0){
    Bus bus;bus.automatic=false;bus.torque[3]=1;bus.goal[3]=2724;
    Clock clock;HoldInitializationOwner owner(policy(true));
    HoldEvidencePublisher publisher;Sink sink;
    assert(publisher.begin(sink,"test-boot","test-hold"));
    for(int i=0;i<10;++i){clock.tick+=110000;publisher.poll(owner,bus,clock,sink);}
    assert(owner.phase()==HoldPhase::Captured&&bus.writes==1&&bus.enables==0);
    assert(sink.records.size()==7);
    for(const auto& record:sink.records)std::cout<<record<<"\n";
    return 0;
  }
  assert(run_owner_cases()==0);
  for(int scenario=0;scenario<3;++scenario){
    Bus bus;bus.automatic=scenario!=1;if(scenario==2)bus.bad=15;
    Clock clock;HoldInitializationOwner owner(policy(scenario==1));
    HoldEvidencePublisher publisher;Sink sink;
    assert(publisher.begin(sink,"test-boot","test-hold"));
    for(int i=0;i<10;++i){clock.tick+=110000;publisher.poll(owner,bus,clock,sink);}
    assert(owner.phase()==(scenario==2?HoldPhase::Fault:HoldPhase::Captured));
    assert(sink.records.size()==size_t(scenario==2?2:(scenario==1?10:7)));
    for(const auto& record:sink.records)std::cout<<record<<"\n";
    char tiny[2]={'x',0};
    assert(!hold_snapshot_json(*owner.scan(0),0,"test-boot","test-hold",tiny,sizeof(tiny))&&tiny[0]==0);
  }
  for(int failure=0;failure<10;++failure){
    Bus bus;bus.automatic=false;Clock clock;HoldInitializationOwner owner(policy(true));
    HoldEvidencePublisher publisher;Sink sink;sink.fail_at=failure;
    assert(publisher.begin(sink,"test-boot","test-hold"));
    for(int i=0;i<10;++i){clock.tick+=110000;publisher.poll(owner,bus,clock,sink);}
    assert(publisher.faulted()&&owner.phase()==HoldPhase::Fault);
    const auto writes=bus.writes+bus.enables;const auto reads=bus.reads;
    publisher.poll(owner,bus,clock,sink);
    assert(reads==bus.reads&&writes==bus.writes+bus.enables);
  }
  {Bus bus;Clock clock;HoldInitializationOwner owner(policy());HoldEvidencePublisher publisher;Sink sink;
   publisher.poll(owner,bus,clock,sink);assert(bus.reads==0&&bus.writes==0&&publisher.faulted());}
  {Bus bus;Clock clock;clock.tick=INT64_MAX-10000;HoldStateSnapshot snapshot;
   assert(snapshot.capture(bus,clock,10000,100000));
   char identity[129],hash[65],raw[4096],linked[4096];
   memset(identity,'x',128);identity[128]=0;memset(hash,'a',64);hash[64]=0;
   assert(hold_snapshot_json(snapshot,7,identity,identity,raw,sizeof(raw)));
   JsonDocument doc;assert(!deserializeJson(doc,raw));
   doc["plan_sha256"]=hash;doc["policy_sha256"]=hash;
   assert(hold_json_finish(doc,linked,sizeof(linked)));
   EvidenceStore<12,4096> store;assert(store.reserve(12)&&store.publish("hold_scan",linked));}
}
