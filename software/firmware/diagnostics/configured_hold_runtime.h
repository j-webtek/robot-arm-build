// Explicit hold-only network composition. No filesystem reads, default policy,
// default port, legacy motion path, or automatic reset/rearm.
#pragma once
#include "hold_listener_owner.h"
#include "start_socket_session.h"
#include "start_listener.h"
#include "controller_hold_config.h"
namespace rocell_diag {
template<class Library,class Clock,class Server,class Client,class Socket,class Crypto,bool Recovery=false,uint8_t RecoveryLimit=5>
class ConfiguredHoldRuntime {
  using Allocated=AllocatedHoldRuntime<Library,Clock,Crypto,Recovery,RecoveryLimit>;
  using Owner=HoldListenerOwner<Allocated>;
  using Connection=StartSocketSession<Owner,Clock,Socket>;
  using Listener=StartListener<Server,Client,Connection,Owner,Clock>;
  struct Network {
    Allocated runtime;Server server;Client client;Socket socket;
    Owner owner;Connection connection;Listener listener;
    Network(Clock& clock,uint16_t port,uint64_t expires)
      :server(port,1),socket(client),owner(runtime),connection(owner,clock,socket),
       listener(server,client,connection,owner,clock,expires){}
    ~Network(){server.end();client.stop();}
  };
 public:
  ConfiguredHoldRuntime()=default;
  ConfiguredHoldRuntime(const ConfiguredHoldRuntime&)=delete;
  ConfiguredHoldRuntime& operator=(const ConfiguredHoldRuntime&)=delete;
  ~ConfiguredHoldRuntime(){delete network_;}
  // Two bounded allocations: network/request graph and runtime/evidence graph.
  static constexpr size_t allocation_bytes(){return sizeof(Network)+Allocated::allocation_bytes();}
  bool initialize_config(Library& bus,Clock& clock,Crypto& crypto,const uint8_t (&key)[32],
      const uint8_t (&boot)[16],const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,
      const char* bytes,size_t length,bool (*healthy)(void*),void* context){
    if(used_)return false;
    // Ordinary persisted hold settings must never opt in to recovery. The
    // recovery route must explicitly construct the reviewed recovery policy.
    if(Recovery){used_=true;return fail("RECOVERY_EXPLICIT_POLICY_REQUIRED");}
    if(!parser_.parse(bytes,length)){used_=true;return fail("HOLD_CONFIGURATION_REJECTED");}
    const auto& config=*parser_.get();
    return initialize(bus,clock,crypto,key,boot,nonce,issued,expires,config.port,
                      config.policy,config.command,healthy,context);
  }
  bool initialize(Library& bus,Clock& clock,Crypto& crypto,const uint8_t (&key)[32],
      const uint8_t (&boot)[16],const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,
      uint16_t port,const HoldInitializationPolicy& policy,const char* command,
      bool (*healthy)(void*),void* context){
    if(used_)return false;used_=true;
    if(Recovery&&(policy.drift!=2||policy.speed!=20||policy.permit_explicit_enable))
      return fail("RECOVERY_POLICY_REJECTED");
    const char* hex="0123456789abcdef";
    for(size_t i=0;i<16;++i){instance_[2*i]=hex[boot[i]>>4];instance_[2*i+1]=hex[boot[i]&15];}
    uint8_t nonzero=0;for(uint8_t byte:key)nonzero|=byte;
    if(port<1024||!nonzero||!valid_identity(command)||!HoldInitializationOwner::policy_valid(policy)||
       issued>INT64_MAX||expires>INT64_MAX||expires<=issued||expires-issued>30000000||
       bus.End!=0||bus.Level!=1||!healthy||!healthy(context))return fail("HOLD_CONFIGURATION_REJECTED");
    const uint64_t now=clock.now_us();
    if(now<issued||now>=expires)return fail("HOLD_CONFIGURATION_EXPIRED");
    network_=new(std::nothrow) Network(clock,port,expires);
    if(!network_)return fail("HOLD_NETWORK_MEMORY_UNAVAILABLE");
    if(!network_->runtime.initialize(bus,clock,crypto,key,boot,nonce,issued,expires,policy,command,healthy,context))
      return fail(network_->runtime.reason());
    if(!network_->listener.begin())return fail(network_->listener.reason());
    return true;
  }
  void poll(){if(network_&&!failure_)network_->listener.poll();}
  bool exclusive_work()const{return network_&&network_->listener.state()==ListenerState::Running&&!failure_;}
  void interference(){if(network_){network_->owner.interference();network_->server.end();network_->client.stop();}fail("HOLD_EXTERNAL_INTERFERENCE");}
  void export_failed(){interference();}
  SessionState state()const{return failure_?SessionState::Fault:network_?network_->owner.state():SessionState::Idle;}
  const char* reason()const{return failure_?failure_:network_?network_->owner.reason():"NOT_CONFIGURED";}
  size_t size()const{return network_?network_->runtime.size():0;}
  bool storage_faulted()const{return network_&&network_->runtime.storage_faulted();}
  // Explicit post-export transition only. Caller must retain/export hold evidence
  // before this destroys it. No bus command, torque release, reset or rearm.
  bool retire_to_pair(VerifiedHoldHandoff& out){
    if(handoff_attempted_)return false;handoff_attempted_=true;
    if(failure_||!network_||network_->listener.state()!=ListenerState::Finished||
       state()!=SessionState::Captured||!network_->runtime.take_handoff(out))return false;
    delete network_;network_=nullptr;
    fail("HOLD_HANDED_OFF"); // Terminal old surface; never exposes stale records.
    return true;
  }
  const typename Allocated::Store::Record* get(size_t index)const{return network_?network_->runtime.get(index):nullptr;}
  bool record_json(size_t index,char* out,size_t capacity)const{
    if(!out||!capacity)return false;out[0]=0;
    const auto* record=get(index);if(!record)return false;
    const int n=snprintf(out,capacity,
      "{\"schema\":\"%s\",\"instance_id\":\"%s\",\"index\":%u,\"kind\":\"%s\",\"record\":%s}",
      Recovery?(RecoveryLimit==6?"rocell.six_count_recovery_record.v1":"rocell.supported_recovery_record.v1"):"rocell.hold_record.v1",
      instance_,unsigned(index),record->kind,record->json);
    if(n<0||size_t(n)>=capacity){out[0]=0;return false;}return true;
  }
  bool status_json(char* out,size_t capacity)const{
    if(!out||!capacity)return false;out[0]=0;
    if(!used_)return false;
    const auto s=state();const char* name=s==SessionState::Idle?"IDLE":s==SessionState::Sampling?"SAMPLING":s==SessionState::Captured?"CAPTURED":"FAULT";
    // Distinct schema prevents old 2304-byte collectors silently accepting it.
    const int n=snprintf(out,capacity,
      "{\"schema\":\"%s\",\"instance_id\":\"%s\",\"state\":\"%s\","
      "\"reason\":\"%s\",\"records\":%u,\"record_bytes\":4096,\"storage_fault\":%s,\"durable_export_verified\":false}",
      Recovery?(RecoveryLimit==6?"rocell.six_count_recovery_transport.v1":"rocell.supported_recovery_transport.v1"):"rocell.hold_transport.v1",
      instance_,name,reason(),unsigned(size()),storage_faulted()?"true":"false");
    if(n<0||size_t(n)>=capacity){out[0]=0;return false;}return true;
  }
 private:
  bool fail(const char* reason){if(!failure_)failure_=reason;return false;}
  Network* network_=nullptr;bool used_=false,handoff_attempted_=false;const char* failure_=nullptr;char instance_[33]={};
  ControllerHoldConfigParser parser_;
};
}
