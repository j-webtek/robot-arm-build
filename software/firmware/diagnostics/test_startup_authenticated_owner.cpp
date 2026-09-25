#include <cassert>
#include <cstring>
#include "startup_authenticated_owner.h"
#include "evidence_store.h"
using namespace rocell_diag;
// Explicit test doubles isolate orchestration; separate suites test real HMAC
// and native parsing. These are never compiled into the controller candidate.
struct Envelope{
 Envelope(const uint8_t(&)[32],const uint8_t(&)[16],const uint8_t(&)[32],uint64_t,uint64_t){}
 template<class Crypto>bool consume(const uint8_t* token,size_t n,uint64_t,Crypto&,AuthenticatedPlanView& view){
  if(n!=1||token[0]!=1)return false;view={token,n};return true;}
};
struct Parser{
 bool parse(const char*,size_t,const char*,const char*,const char*,const StartupPositionPolicy&,uint8_t,const WholeArmBaselinePolicy&){return true;}
 template<class Crypto,class Converter>bool bind_payload(Crypto&,Converter&){return true;}
 bool copy_bound_request(BoundStartRequest& r)const{
  const char payload[]="{\"T\":101,\"acc\":1,\"joint\":3,\"rad\":1.5,\"spd\":20}";
  memcpy(r.boot,"00000000000000000000000000000000",33);memcpy(r.command,"command",8);
  memcpy(r.payload,payload,sizeof(payload));r.payload_length=sizeof(payload)-1;
  r.wire_count=2008;r.desired_count=2008;r.maximum_delta=8;r.samples=1;r.pair_us=100;r.interval_us=1000;return true;
 }
};
struct Clock{uint64_t tick=100;uint64_t now_us(){return ++tick;}};
struct Crypto{bool sha256(const uint8_t*,size_t,uint8_t (&out)[32]){memset(out,1,32);return true;}};
struct TestConverter{bool admit_and_convert(double,uint16_t,uint8_t,uint16_t& target){target=2008;return true;}};
struct Bus{
 int End=0,Level=1,Error=0,reads=0,writes=0;bool torque=true,mismatch=false,ack_fail=false;
 int Read(uint8_t,uint8_t address,uint8_t* bytes,uint8_t width){
  ++reads;unsigned value=address==56?(writes?2008:2000):address==42?(writes&&!mismatch?2008:0):address==40&&torque?1:0;
  bytes[0]=value&255;if(width>1)bytes[1]=value>>8;return width;
 }
 int WritePosEx(uint8_t id,int16_t target,uint16_t speed,uint8_t acc){
  assert(id==14&&target==2008&&speed==20&&acc==1);++writes;return ack_fail?0:1;
 }
};
struct Sink{
 EvidenceStore<16,2304> store;int calls=0,fail_at=-1;
 bool reserve(size_t n){return store.reserve(n);}bool faulted()const{return store.faulted();}
 bool publish(const char* kind,const char* json){if(calls++==fail_at)return false;return store.publish(kind,json);}
};
bool fault(void* context){return *static_cast<bool*>(context);}
int main(){
 for(int mode=0;mode<12;++mode){
  Bus bus;Clock clock;Sink sink;TestConverter converter;Crypto crypto;bool external=false;
  uint8_t key[32]={1},boot[16]={},nonce[32]={1},token=mode==1?0:1;
  StartupPositionPolicy p={};for(auto& w:p.joints)w={1990,2010};p.drift_tolerance=2;
  p.minimum_separation_us=100000;p.maximum_wait_us=1000000;p.maximum_pair_us=10000;
  p.maximum_scan_us=100000;p.maximum_age_us=100000;WholeArmBaselinePolicy normal={};
  if(mode==2)bus.torque=false;if(mode==3)sink.fail_at=3;if(mode==4)bus.Level=0;
  if(mode==6)bus.mismatch=true;if(mode==7)bus.ack_fail=true;if(mode==8)sink.fail_at=5;
  StartupAuthenticatedOwner<Bus,Clock,Sink,TestConverter,Crypto,Parser,Envelope> owner(
    bus,clock,sink,converter,crypto,key,boot,nonce,1,2000000,"conversion","policy",p,0,normal,fault,&external);
  const bool accepted=owner.start(&token,1);assert(accepted==(mode!=1&&mode!=4));
  assert(bus.writes==0);owner.poll();assert(bus.writes==0);
  if(mode==5)external=true;
  // Admission cannot survive lease expiration, clock reversal, or interference.
  if(mode==9)clock.tick=2000000;
  if(mode==10){clock.tick=0;owner.poll();}
  if(mode==11)owner.interference();
  clock.tick+=100000;owner.poll();
  if(mode==0||mode==6||mode==7){assert(bus.writes==1);clock.tick+=1000;owner.poll();
    assert(owner.state()==(mode==0?StartupOwnerState::Captured:StartupOwnerState::Fault));
    if(mode==6)assert(!strcmp(owner.reason(),"TARGET_READBACK_MISMATCH"));
  }else{assert(bus.writes==0&&owner.state()==StartupOwnerState::Fault);}
  const int before=bus.writes;owner.poll();assert(bus.writes==before&&!owner.start(&token,1));
 }
}
