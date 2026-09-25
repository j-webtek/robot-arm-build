#include "held_pair_network_operation.h"
#include <cassert>
#include <string>
#include <vector>
#include <memory>
using namespace rocell_diag;
struct Scenario {
  std::vector<uint8_t> bytes;size_t offset=0;int accepts=0,begins=0,ends=0,sends=0;
  bool closed=false,short_reply=false,bind_ok=true,delivered=false;
};
static Scenario scene;
struct Client {int descriptor=-1;int fd(){return descriptor;}void stop(){descriptor=-1;scene.closed=true;}};
struct Server {
  Server(uint16_t,int){}void begin(){++scene.begins;}void end(){++scene.ends;}
  explicit operator bool(){return scene.bind_ok;}
  Client accept(){++scene.accepts;if(scene.delivered)return {};scene.delivered=true;return {1};}
};
struct Socket {
  Client& client;explicit Socket(Client& c):client(c){}
  int receive(uint8_t* out,size_t maximum){
    if(scene.offset==scene.bytes.size())return -2;
    size_t n=std::min(maximum,scene.bytes.size()-scene.offset);
    memcpy(out,scene.bytes.data()+scene.offset,n);scene.offset+=n;return int(n);
  }
  int send_once(const uint8_t*,size_t n){++scene.sends;return int(n)-(scene.short_reply?1:0);}
  void close(){client.stop();}
};
struct Clock {uint64_t tick=1000;uint64_t now_us(){return ++tick;}};
// This fixture isolates network scheduling; real HMAC/pair integration is tested
// separately by test_held_pair_authenticated_runtime.cpp.
struct Runtime {
  HeldPairPhase current=HeldPairPhase::New;int polls=0;bool returning=false;
  HeldPairPhase phase()const{return current;}const char* reason()const{return "TEST";}
  void interference(){current=HeldPairPhase::Stopped;}
  void poll(){assert(scene.closed);++polls;current=returning?HeldPairPhase::Complete:HeldPairPhase::AwaitingExport;}
};
struct Operation {
  Runtime& runtime;bool start(const uint8_t*,size_t){
    runtime.current=runtime.returning?HeldPairPhase::Return:HeldPairPhase::Forward;return true;
  }
};
#ifndef HELD_NETWORK_NO_MAIN
int main(){
  for(bool returning:{false,true})for(int fault=0;fault<5;++fault){
    scene=Scenario{};Runtime runtime;runtime.returning=returning;
    if(returning)runtime.current=HeldPairPhase::AwaitingExport;
    Clock clock;Operation operation{runtime};
    std::string header="POST /rocell/diagnostics/start HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/octet-stream\r\nConnection: close\r\nContent-Length: 256\r\n\r\n";
    if(fault==3)header.replace(0,4,"GET ");
    scene.bytes.assign(header.begin(),header.end());scene.bytes.insert(scene.bytes.end(),256,1);
    scene.short_reply=fault==1;scene.bind_ok=fault!=2;
    using Network=HeldPairNetworkOperation<Runtime,Operation,Clock,Server,Client,Socket>;
    auto network=std::unique_ptr<Network>(new Network(runtime,operation,clock,fault==4?80:8081,10000000,returning));
    const bool began=network->begin();assert(began==(fault!=2&&fault!=4));
    assert(!network->begin());
    for(int i=0;i<30;++i){clock.tick+=1000;network->poll();}
    if(fault==0){assert(network->state()==ListenerState::Finished&&runtime.polls==1&&scene.accepts==1);}
    else{assert(network->state()==ListenerState::Fault&&runtime.polls==0);}
    const int accepts=scene.accepts,polls=runtime.polls;
    for(int i=0;i<30;++i)network->poll();
    assert(scene.accepts==accepts&&runtime.polls==polls);
  }
  return 0;
}
#endif
