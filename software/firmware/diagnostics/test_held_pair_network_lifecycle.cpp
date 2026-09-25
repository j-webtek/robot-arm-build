#define HELD_NETWORK_NO_MAIN
#include "test_held_pair_network_operation.cpp"
#include "held_pair_network_lifecycle.h"
struct LifecycleRuntime:Runtime{
  const char* boot_id()const{return "11111111111111111111111111111111";}
  bool start(HeldPairPlanAdmission&,const uint8_t*,size_t,VerifiedHoldHandoff&){current=HeldPairPhase::Forward;return true;}
  bool admit_return(HeldReturnAdmission&,const uint8_t*,size_t){returning=true;current=HeldPairPhase::Return;return true;}
};
struct Entropy {int calls=0;bool fail=false,repeated=false;
  bool fill(uint8_t* out,size_t n){++calls;if(fail)return false;memset(out,repeated?1:calls,n);return true;}};
void request(){
  scene=Scenario{};
  std::string header="POST /rocell/diagnostics/start HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/octet-stream\r\nConnection: close\r\nContent-Length: 256\r\n\r\n";
  scene.bytes.assign(header.begin(),header.end());scene.bytes.insert(scene.bytes.end(),256,1);
}
int main(){
  for(int fault=0;fault<6;++fault){
    request();LifecycleRuntime runtime;Clock clock;Entropy entropy;VerifiedHoldHandoff handoff;
    uint8_t key[32],boot[16];memset(key,'k',32);memset(boot,0x11,16);
    using Lifecycle=HeldPairNetworkLifecycle<LifecycleRuntime,Clock,Entropy,Server,Client,Socket>;
    auto lifecycle=std::unique_ptr<Lifecycle>(new Lifecycle(runtime,handoff,clock,entropy,8081,key,boot));
    char first[512],second[512];assert(!lifecycle->issue_return(second,sizeof(second)));
    if(fault==1)entropy.fail=true;
    assert(lifecycle->issue_initial(first,fault==2?1:sizeof(first))==(fault!=1&&fault!=2));
    assert(!lifecycle->issue_initial(first,sizeof(first)));
    if(fault==1||fault==2){assert(lifecycle->phase()==PairNetworkPhase::Fault&&scene.begins==0);continue;}
    if(fault==3)clock.tick+=11000000;
    for(int i=0;i<30;++i){clock.tick+=1000;lifecycle->poll();}
    if(fault==3){assert(lifecycle->phase()==PairNetworkPhase::Fault&&runtime.polls==0);continue;}
    assert(lifecycle->phase()==PairNetworkPhase::AwaitReturn&&runtime.polls==1);
    const int accepts=scene.accepts,calls=entropy.calls;
    for(int i=0;i<30;++i)lifecycle->poll();
    assert(scene.accepts==accepts&&entropy.calls==calls); // No automatic return.
    request();if(fault==4)entropy.repeated=true;if(fault==5)clock.tick=100;
    bool ok=lifecycle->issue_return(second,sizeof(second));
    assert(ok==(fault==0));
    if(!ok){assert(lifecycle->phase()==PairNetworkPhase::Fault&&runtime.polls==1);continue;}
    JsonDocument a,b;assert(!deserializeJson(a,first)&&!deserializeJson(b,second));
    assert(strcmp(a["nonce"].as<const char*>(),b["nonce"].as<const char*>()));
    for(int i=0;i<30;++i){clock.tick+=1000;lifecycle->poll();}
    assert(lifecycle->phase()==PairNetworkPhase::Complete&&runtime.polls==2);
    assert(!lifecycle->issue_return(second,sizeof(second)));
  }
  return 0;
}
