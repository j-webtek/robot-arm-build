#include "received_session.h"
#include "evidence_store.h"
#include <cassert>
#include <cstdio>
using namespace rocell_diag;
struct Clock{uint64_t t=1000;uint64_t now_us(){return ++t;}};
struct Bus{
  int Level=1,End=0,Error=0,writes=0;
  int WritePosEx(uint8_t id,int16_t target,uint16_t speed,uint8_t acc){
    assert(id==14 && target==2100 && speed==20 && acc==1);++writes;return 1;
  }
  int Read(uint8_t,uint8_t,uint8_t* data,uint8_t n){data[0]=0x34;data[1]=0x08;return n;}
};
struct FakeAdmission{
  bool allow=true;int calls=0;
  bool admit_and_convert(double rad,uint16_t speed,uint8_t acc,uint16_t& target){
    ++calls;assert(fabs(rad-1.7)<1e-7 && speed==20 && acc==1);target=2100;return allow;
  }
};
int main(){
  const char* payload="{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1}";
  Bus bus;Clock clock;FakeAdmission converter;EvidenceStore<8> store;ReceivedSession session;
  assert(session.start(bus,clock,store,converter,"boot","command",payload,strlen(payload),3,100));
  for(int i=0;i<3;++i){clock.t+=1000000;assert(session.sample(bus,clock,store));}
  assert(bus.writes==1 && converter.calls==1 && store.size()==8);
  for(size_t i=0;i<store.size();++i)puts(store.get(i)->json);
  assert(!session.start(bus,clock,store,converter,"boot","other",payload,strlen(payload),3,100));
  assert(bus.writes==1 && converter.calls==1);
  Bus limited_bus;FakeAdmission limited_converter;EvidenceStore<4> limited;ReceivedSession rejected;
  assert(!rejected.start(limited_bus,clock,limited,limited_converter,"boot","limited",payload,strlen(payload),1,100));
  assert(limited_bus.writes==0 && limited_converter.calls==0);
  Bus denied_bus;FakeAdmission denied;denied.allow=false;EvidenceStore<8> denied_store;ReceivedSession denial;
  assert(!denial.start(denied_bus,clock,denied_store,denied,"boot","denied",payload,strlen(payload),1,100));
  assert(denied_bus.writes==0 && denied_store.size()==1);
}
