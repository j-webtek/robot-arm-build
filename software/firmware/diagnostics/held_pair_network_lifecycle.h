// Explicit two-operation coordinator. Caller requests each challenge; polling
// never issues one or rearms a listener. Runtime/handoff/clock/entropy outlive it.
#pragma once
#include "held_pair_network_operation.h"
namespace rocell_diag {
enum class PairNetworkPhase { New, Initial, AwaitReturn, Returning, Complete, Fault };
template<class Runtime,class Clock,class Entropy,class Server,class Client,class Socket>
class HeldPairNetworkLifecycle {
  using InitialOperation=HeldPairInitialOperation<Runtime>;
  using ReturnOperation=HeldPairReturnOperation<Runtime>;
  template<class Operation> using Network=HeldPairNetworkOperation<Runtime,Operation,Clock,Server,Client,Socket>;
  struct InitialGraph {
    HeldPairPlanAdmission gate;InitialOperation operation;Network<InitialOperation> network;
    InitialGraph(Runtime& runtime,VerifiedHoldHandoff& held,Clock& clock,uint16_t port,
        const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires)
        :gate(key,boot,nonce,issued,expires),operation{runtime,gate,held},network(runtime,operation,clock,port,expires,false){}
  };
  struct ReturnGraph {
    HeldReturnAdmission gate;ReturnOperation operation;Network<ReturnOperation> network;
    ReturnGraph(Runtime& runtime,Clock& clock,uint16_t port,
        const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires)
        :gate(key,boot,nonce,issued,expires),operation{runtime,gate},network(runtime,operation,clock,port,expires,true){}
  };
 public:
  HeldPairNetworkLifecycle(Runtime& runtime,VerifiedHoldHandoff& held,Clock& clock,Entropy& entropy,
      uint16_t port,const uint8_t (&key)[32],const uint8_t (&boot)[16],uint64_t lease=10000000)
      :runtime_(runtime),held_(held),clock_(clock),entropy_(entropy),port_(port),lease_(lease){
    memcpy(key_,key,32);memcpy(boot_,boot,16);
    const char* hex="0123456789abcdef";
    for(size_t i=0;i<16;++i){boot_text_[2*i]=hex[boot[i]>>4];boot_text_[2*i+1]=hex[boot[i]&15];}
  }
  HeldPairNetworkLifecycle(const HeldPairNetworkLifecycle&)=delete;
  HeldPairNetworkLifecycle& operator=(const HeldPairNetworkLifecycle&)=delete;
  ~HeldPairNetworkLifecycle(){
    if(phase_==PairNetworkPhase::Initial||phase_==PairNetworkPhase::AwaitReturn||phase_==PairNetworkPhase::Returning)
      runtime_.interference(); // Logical stop only; never release torque.
    initial_.reset();returning_.reset();
    volatile uint8_t* p=key_;for(size_t i=0;i<32;++i)p[i]=0;
  }
  bool issue_initial(char* out,size_t capacity){
    if(phase_!=PairNetworkPhase::New)return false;
    if(runtime_.phase()!=HeldPairPhase::New||!prepare(out,capacity,false))return fail();
    initial_.reset(new(std::nothrow) InitialGraph(runtime_,held_,clock_,port_,key_,boot_,nonce_,issued_,expires_));
    if(!initial_||!initial_->network.begin()){if(out&&capacity)out[0]=0;return fail();}
    phase_=PairNetworkPhase::Initial;return true;
  }
  bool issue_return(char* out,size_t capacity){
    if(phase_!=PairNetworkPhase::AwaitReturn)return false;
    if(runtime_.phase()!=HeldPairPhase::AwaitingExport||!prepare(out,capacity,true))return fail();
    returning_.reset(new(std::nothrow) ReturnGraph(runtime_,clock_,port_,key_,boot_,nonce_,issued_,expires_));
    if(!returning_||!returning_->network.begin()){if(out&&capacity)out[0]=0;return fail();}
    phase_=PairNetworkPhase::Returning;return true;
  }
  void poll(){
    if(phase_==PairNetworkPhase::New||phase_==PairNetworkPhase::Complete||phase_==PairNetworkPhase::Fault)return;
    const uint64_t now=clock_.now_us();
    if(now<last_clock_||now>INT64_MAX){fail();return;}last_clock_=now;
    if(phase_==PairNetworkPhase::Initial){
      initial_->network.poll();const auto state=initial_->network.state();
      if(state==ListenerState::Fault){fail();return;}
      if(state==ListenerState::Finished){initial_.reset();phase_=PairNetworkPhase::AwaitReturn;}
    }else if(phase_==PairNetworkPhase::Returning){
      returning_->network.poll();const auto state=returning_->network.state();
      if(state==ListenerState::Fault){fail();return;}
      if(state==ListenerState::Finished){returning_.reset();phase_=PairNetworkPhase::Complete;}
    }
  }
  PairNetworkPhase phase()const{return phase_;}
  static constexpr size_t initial_graph_bytes(){return sizeof(InitialGraph);}
  static constexpr size_t return_graph_bytes(){return sizeof(ReturnGraph);}
 private:
  bool prepare(char* out,size_t capacity,bool returning){
    if(out&&capacity)out[0]=0;
    uint8_t nonzero=0;for(uint8_t b:key_)nonzero|=b;
    if(!out||!capacity||!nonzero||port_<1024||!lease_||lease_>30000000||
       strcmp(runtime_.boot_id(),boot_text_))return false;
    issued_=clock_.now_us();
    if(issued_<last_clock_||issued_>INT64_MAX||lease_>uint64_t(INT64_MAX)-issued_)return false;
    last_clock_=issued_;
    uint8_t previous[32];memcpy(previous,nonce_,32);
    if(!entropy_.fill(nonce_,32))return false;
    nonzero=0;for(uint8_t b:nonce_)nonzero|=b;
    if(!nonzero||(returning&&!memcmp(previous,nonce_,32)))return false;
    expires_=issued_+lease_;
    char nonce_text[65]={};const char* hex="0123456789abcdef";
    for(size_t i=0;i<32;++i){nonce_text[2*i]=hex[nonce_[i]>>4];nonce_text[2*i+1]=hex[nonce_[i]&15];}
    JsonDocument doc;doc["schema"]="rocell.start_challenge.v1";doc["boot_id"]=boot_text_;
    doc["nonce"]=nonce_text;doc["issued_us"]=issued_;doc["expires_us"]=expires_;
    return hold_json_finish(doc,out,capacity);
  }
  bool fail(){initial_.reset();returning_.reset();runtime_.interference();phase_=PairNetworkPhase::Fault;return false;}
  Runtime& runtime_;VerifiedHoldHandoff& held_;Clock& clock_;Entropy& entropy_;
  uint16_t port_;uint64_t lease_,issued_=0,expires_=0,last_clock_=0;
  uint8_t key_[32]={},boot_[16]={},nonce_[32]={};char boot_text_[33]={};
  std::unique_ptr<InitialGraph> initial_;std::unique_ptr<ReturnGraph> returning_;
  PairNetworkPhase phase_=PairNetworkPhase::New;
};
}
