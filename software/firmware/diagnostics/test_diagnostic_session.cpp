#include "diagnostic_session.h"
#include "evidence_store.h"
#include <cassert>
#include <string>
#include <vector>
using namespace rocell_diag;
struct Clock { uint64_t t=1000;uint64_t now_us(){return ++t;} };
struct Library {
  int Level=1,End=0,Error=0,writes=0,reads=0,result=1;bool bad_read=false,wrong_target=false;
  int WritePosEx(uint8_t,int16_t,uint16_t,uint8_t){++writes;return result;}
  int Read(uint8_t,uint8_t address,uint8_t* data,uint8_t width){
    ++reads;data[0]=(wrong_target && address==42)?0x35:0x34;data[1]=0x08;return bad_read?0:width;
  }
};
struct Sink {
  bool reserve(size_t) {return true;}
  int calls=0,fail_at=0;std::vector<std::string> kinds;
  bool publish(const char* kind,const char*){
    ++calls;if(calls==fail_at)return false;kinds.emplace_back(kind);return true;
  }
};
int main(){
  {
    Library bus;Clock clock;EvidenceStore<8> evidence;DiagnosticSession session;
    assert(session.start(bus,clock,evidence,"boot","wrong-target",14,2100,20,1,3,100));
    bus.wrong_target=true;clock.t+=1000000;
    assert(!session.sample(bus,clock,evidence));
    assert(session.state()==SessionState::Fault && !strcmp(session.reason(),"TARGET_READBACK_MISMATCH"));
    assert(bus.writes==1 && bus.reads==2 && evidence.size()==5);
    assert(!strcmp(evidence.get(4)->kind,"pair"));
    assert(strstr(evidence.get(4)->json,"3508")!=nullptr);
    clock.t+=1000000;assert(!session.sample(bus,clock,evidence));
    assert(bus.writes==1 && bus.reads==2 && evidence.size()==5);
  }
  for(int scenario=0;scenario<10;++scenario){
    Library bus;Clock clock;Sink sink;DiagnosticSession session;
    if(scenario==1)sink.fail_at=1;
    if(scenario==2)sink.fail_at=3;
    if(scenario==3)bus.result=0;
    if(scenario==9)bus.End=1;
    bool started=session.start(bus,clock,sink,"boot","command",14,2100,20,1,2,100);
    if((scenario>=1 && scenario<=3) || scenario==9){
      assert(!started && session.state()==SessionState::Fault);
      assert(bus.writes==((scenario==1 || scenario==9)?0:1));
    } else {
      assert(started);
      if(scenario==4)session.interference();
      if(scenario==5)session.export_failed();
      if(scenario==6)assert(!session.start(bus,clock,sink,"boot","duplicate",14,2100,20,1,2,100));
      if(scenario==7)bus.bad_read=true;
      if(scenario==8)sink.fail_at=5;
      clock.t+=1000000;
      bool sampled=session.sample(bus,clock,sink);
      if(scenario>=4 && scenario<=8)assert(!sampled && session.state()==SessionState::Fault);
      else {
        assert(sampled);clock.t+=1000000;assert(session.sample(bus,clock,sink));
        assert(session.state()==SessionState::Captured && bus.reads==4);
      }
      assert(bus.writes==1);
    }
    const int reads=bus.reads,writes=bus.writes;
    assert(!session.sample(bus,clock,sink));
    assert(bus.reads==reads && bus.writes==writes);
  }
  Library bus;Clock clock;EvidenceStore<8> store;DiagnosticSession session;
  assert(session.start(bus,clock,store,"simulation-boot","simulation-command",14,2100,20,1,3,100));
  for(int i=0;i<3;++i){clock.t+=1000000;assert(session.sample(bus,clock,store));}
  assert(store.size()==7 && session.state()==SessionState::Captured);
  for(size_t i=0;i<store.size();++i)puts(store.get(i)->json);
  assert(store.get(7)==nullptr);
  Library limited_bus;EvidenceStore<4> limited;DiagnosticSession rejected;
  assert(!rejected.start(limited_bus,clock,limited,"boot","limited",14,2100,20,1,1,100));
  assert(limited_bus.writes==0 && limited.faulted());
  EvidenceStore<4,256> overflow;
  char original[]="{}";
  assert(overflow.publish("pair",original));original[0]='!';
  assert(strcmp(overflow.get(0)->json,"{}")==0);
  for(int i=0;i<3;++i)assert(overflow.publish("pair","{}"));
  assert(!overflow.publish("pair","{}") && overflow.faulted());
  assert(overflow.size()==4 && strcmp(overflow.get(0)->json,"{}")==0);
  for(int timing_case=0;timing_case<3;++timing_case){
    Library timed_bus;Clock timed_clock;Sink timed_sink;DiagnosticSession timed;
    assert(timed.start(timed_bus,timed_clock,timed_sink,"boot","timed",14,2100,20,1,2,100));
    assert(!timed.sample(timed_bus,timed_clock,timed_sink));
    assert(timed.state()==SessionState::Sampling && timed_bus.reads==0);
    if(timing_case==0)timed_clock.t+=3000000;
    if(timing_case==1)timed_clock.t=0;
    if(timing_case==2){
      timed_clock.t+=1000000;assert(timed.sample(timed_bus,timed_clock,timed_sink));
      assert(!timed.sample(timed_bus,timed_clock,timed_sink));
      assert(timed.state()==SessionState::Sampling && timed_bus.reads==2);
    }else{
      assert(!timed.sample(timed_bus,timed_clock,timed_sink));
      assert(timed.state()==SessionState::Fault && timed_bus.reads==0);
      assert(strcmp(timed.reason(),timing_case==0?"MISSED_SAMPLE_DEADLINE":"INVALID_CLOCK")==0);
    }
    assert(timed_bus.writes==1);
  }
}
