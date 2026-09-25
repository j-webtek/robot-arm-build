#include <cassert>
#include <cstring>
#include "whole_arm_baseline.h"
#include "received_session.h"
#include "evidence_store.h"
struct Clock{uint64_t tick=1000;uint64_t now_us(){return ++tick;}};
struct Bus {
  int End=0,Level=1,Error=0,reads=0,writes=0;
  int Read(uint8_t,uint8_t,uint8_t* data,uint8_t width){++reads;data[0]=0x34;data[1]=0x08;return width;}
  int WritePosEx(uint8_t,int16_t,uint16_t,uint8_t){++writes;return 1;}
};
struct TestConverter {
  bool admit_and_convert(double,uint16_t,uint8_t,uint16_t& target){target=2100;return true;}
};
struct Sink {
  rocell_diag::EvidenceStore<16> store;Clock& clock;bool& fault;int mode;
  bool reserve(size_t count){return store.reserve(count);}
  bool publish(const char* kind,const char* record){
    if(strcmp(kind,"converted")==0){
      if(mode==1)clock.tick+=200;
      if(mode==3)fault=true;
      if(mode==4)return false;
    }
    return store.publish(kind,record);
  }
};
struct Boundary {
  rocell_diag::WholeArmBaseline& baseline;bool& fault;uint64_t expires;int calls=0;
  static bool check(void* context,uint64_t now){
    auto& self=*static_cast<Boundary*>(context);++self.calls;
    return !self.fault && now<self.expires && self.baseline.fresh(now);
  }
};
int main(){
  for(int mode=0;mode<5;++mode){
    Bus bus;Clock clock;bool fault=false;rocell_diag::WholeArmBaselinePolicy policy={};
    for(auto& window:policy.joints)window={2090,2110};
    policy.tracking_tolerance=2;policy.maximum_pair_us=100;
    policy.maximum_scan_us=1000;policy.maximum_age_us=100;
    rocell_diag::WholeArmBaseline baseline(policy);assert(baseline.check(bus,clock));
    assert(bus.reads==14 && bus.writes==0);
    Boundary boundary{baseline,fault,mode==2?1030u:10000u,0};
    rocell_diag::WriteBoundaryGuard guard{&Boundary::check,&boundary};
    Sink sink{{},clock,fault,mode};TestConverter converter;rocell_diag::ReceivedSession session;
    const char* payload="{\"T\":101,\"joint\":3,\"rad\":1.7,\"spd\":20,\"acc\":1}";
    bool ok=session.start(bus,clock,sink,converter,"boot","command",payload,strlen(payload),3,100,1000,guard);
    assert(ok==(mode==0) && bus.writes==(mode==0?1:0));
    assert(boundary.calls==(mode==4?0:1));
    if(mode>=1 && mode<=3){
      assert(strcmp(session.reason(),"WRITE_NOT_ATTEMPTED")==0);
      assert(sink.store.size()==3); // Receipt, conversion, rejected hook; no invented ACK.
      assert(strstr(sink.store.get(2)->json,"PREWRITE_REJECTED"));
      assert(strstr(sink.store.get(2)->json,"\"write_attempted\":false"));
    }
    int before=bus.writes;
    assert(!session.start(bus,clock,sink,converter,"boot","retry",payload,strlen(payload),3,100,1000,guard));
    assert(bus.writes==before && bus.reads==14);
  }
}
