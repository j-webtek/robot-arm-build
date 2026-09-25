#include <new>
// Fail each explicit object-graph allocation independently. Ordinary STL/JSON
// allocations are not replaced by this test hook.
unsigned configured_allocations=0,fail_configured_allocation=0;
bool fail_configured_listener=false;
void* operator new(size_t size,const std::nothrow_t&) noexcept {
 ++configured_allocations;
 if(configured_allocations==fail_configured_allocation)return nullptr;
 try{return ::operator new(size);}catch(...){return nullptr;}
}
void operator delete(void* value,const std::nothrow_t&) noexcept {::operator delete(value);}
#define HOLD_LISTENER_NO_MAIN
#include "test_hold_listener.cpp"
#undef HOLD_LISTENER_NO_MAIN
#include "configured_hold_runtime.h"
#include "configured_held_pair_runtime.h"
struct PairEntropy {bool fill(uint8_t* out,size_t n){memset(out,0x55,n);return true;}};
Network* current_network=nullptr;
struct ConfigServer:Server {
 ConfigServer(uint16_t port,int backlog):Server{*current_network}{assert(port==8081&&backlog==1);}
 void begin(){if(!fail_configured_listener)Server::begin();}
};
#ifndef CONFIGURED_HOLD_NO_MAIN
int main(int argc,char** argv){using namespace rocell_diag;
 assert(argc==2);std::ifstream file(argv[1],std::ios::binary);
 std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
 uint8_t key[32],boot[16],nonce[32];memset(key,'k',32);memset(boot,0x11,16);memset(nonce,0x22,32);
 using Configured=ConfiguredHoldRuntime<GuardedBus,Clock,ConfigServer,Client,Socket,Crypto>;
 for(int failure=1;failure<=3;++failure){
  Network net;current_network=&net;GuardedBus bus;Clock clock;clock.tick=1001;Crypto crypto;
  bool healthy=true;bus.healthy=&healthy;
  configured_allocations=0;fail_configured_allocation=failure<=2?failure:0;
  fail_configured_listener=failure==3;
  Configured runtime;
  assert(!runtime.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,8081,
    policy(),"reviewed-hold",healthy_runtime,&healthy));
  assert(!strcmp(runtime.reason(),failure==1?"HOLD_NETWORK_MEMORY_UNAVAILABLE":
    failure==2?"HOLD_MEMORY_UNAVAILABLE":"LISTENER_START_FAILED"));
  assert(configured_allocations==unsigned(failure==1?1:2));
  assert(runtime.state()==SessionState::Fault&&!runtime.exclusive_work());
  // Memory becoming available must not silently revive the consumed attempt.
  fail_configured_allocation=0;fail_configured_listener=false;
  assert(!runtime.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,8081,
    policy(),"reviewed-hold",healthy_runtime,&healthy));
  for(int i=0;i<20;++i)runtime.poll();
  assert(bus.reads==0&&bus.writes==0&&net.accepts==0&&net.replies==0&&runtime.size()==0);
 }
 for(int scenario=0;scenario<4;++scenario){
  Network net;current_network=&net;GuardedBus bus;Clock clock;clock.tick=1001;Crypto crypto;
  bool healthy=true;bus.healthy=&healthy;
  std::string header="POST /rocell/diagnostics/start HTTP/1.1\r\nHost: test\r\nConnection: close\r\nContent-Type: application/octet-stream\r\nContent-Length: "+
    std::to_string(token.size())+"\r\n\r\n";
  net.request.assign(header.begin(),header.end());net.request.insert(net.request.end(),token.begin(),token.end());
  Configured runtime;char status[512];assert(!runtime.status_json(status,sizeof(status)));
  char policy_text[1536],configuration[2048];assert(hold_policy_json(policy(),policy_text,sizeof(policy_text)));
  JsonDocument config,p;assert(!deserializeJson(p,policy_text));
  config["command_id"]="reviewed-hold";config["hold_policy"].set(p.as<JsonVariantConst>());
  config["schema"]="rocell.controller_hold.v1";config["start_port"]=8081;
  assert(hold_json_finish(config,configuration,sizeof(configuration)));
  assert(runtime.initialize_config(bus,clock,crypto,key,boot,nonce,1000,10001000,
    configuration,strlen(configuration),healthy_runtime,&healthy));
  assert(!runtime.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,8081,
    policy(),"reviewed-hold",healthy_runtime,&healthy));
  assert(bus.reads==0&&bus.writes==0&&runtime.size()==0);
  assert(runtime.status_json(status,sizeof(status)));assert(strstr(status,"rocell.hold_transport.v1"));
  if(scenario==1)net.eof=true;
  if(scenario==2)clock.tick=10001000;
  if(scenario==3)runtime.interference();
  for(int i=0;i<100;++i){clock.tick+=20000;runtime.poll();}
  if(scenario==0){
    assert(runtime.state()==SessionState::Captured&&runtime.size()==8&&bus.writes==1);
    const int reads=bus.reads;
    for(size_t i=0;i<runtime.size();++i)assert(runtime.get(i)&&runtime.get(i)->json[0]=='{');
    assert(!runtime.get(runtime.size()));assert(runtime.status_json(status,sizeof(status)));
    assert(reads==bus.reads);assert(strstr(status,"\"record_bytes\":4096"));
    std::cout<<status<<"\n";
    char record[4608];
    for(size_t i=0;i<runtime.size();++i){assert(runtime.record_json(i,record,sizeof(record)));std::cout<<record<<"\n";}
    assert(!runtime.record_json(runtime.size(),record,sizeof(record))&&record[0]==0);
    char tiny[2];assert(!runtime.record_json(0,tiny,sizeof(tiny))&&tiny[0]==0);
    assert(reads==bus.reads);
  }else assert(runtime.state()==SessionState::Fault&&bus.writes==0);
  assert(!runtime.exclusive_work());
 }
 // Transition retires hold memory first, never releases torque, and never sends
 // displacement merely by creating the pair runtime or issuing a challenge.
 for(unsigned failure=0;failure<=3;++failure){
  Network net;current_network=&net;GuardedBus bus;Clock clock;clock.tick=1001;Crypto crypto;
  bool healthy=true;bus.healthy=&healthy;PairEntropy entropy;
  std::string header="POST /rocell/diagnostics/start HTTP/1.1\r\nHost: test\r\nConnection: close\r\nContent-Type: application/octet-stream\r\nContent-Length: "+
    std::to_string(token.size())+"\r\n\r\n";
  net.request.assign(header.begin(),header.end());net.request.insert(net.request.end(),token.begin(),token.end());
  Configured hold;
  configured_allocations=0;fail_configured_allocation=0;
  assert(hold.initialize(bus,clock,crypto,key,boot,nonce,1000,10001000,8081,
      policy(),"reviewed-hold",healthy_runtime,&healthy));
  for(int i=0;i<100;++i){clock.tick+=20000;hold.poll();}
  assert(hold.state()==SessionState::Captured&&bus.writes==1);
  const int reads=bus.reads;
  using Pair=ConfiguredHeldPairRuntime<GuardedBus,Clock,Crypto,PairEntropy,ConfigServer,Client,Socket>;
  Pair pair;configured_allocations=0;fail_configured_allocation=failure;
  const bool ready=pair.initialize_from_hold(hold,bus,clock,crypto,entropy,policy(),key,boot,
      8081,"forward","return",6,2,healthy_runtime,&healthy);
  assert(ready==(failure==0||failure==3));
  assert(hold.size()==0&&!hold.get(0)&&!strcmp(hold.reason(),"HOLD_HANDED_OFF"));
  VerifiedHoldHandoff again;assert(!hold.retire_to_pair(again));
  assert(!pair.initialize_from_hold(hold,bus,clock,crypto,entropy,policy(),key,boot,
      8081,"forward","return",6,2,healthy_runtime,&healthy));
  char challenge[512];
  if(ready){assert(!pair.issue_return(challenge,sizeof(challenge)));
    assert(pair.issue_initial(challenge,sizeof(challenge))==(failure==0));}
  fail_configured_allocation=0;
  assert(!pair.issue_initial(challenge,sizeof(challenge)));
  for(int i=0;i<20;++i){clock.tick+=1000000;hold.poll();pair.poll();}
  assert(bus.reads==reads&&bus.writes==1&&bus.torque[3]==1);
  assert(pair.phase()==PairNetworkPhase::Fault&&!pair.exclusive_work());
 }
}
#endif
