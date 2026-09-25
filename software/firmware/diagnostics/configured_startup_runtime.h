// Single-lifetime startup runtime with one bounded heap allocation after policy
// validation. ESP32 static DRAM cannot hold the whole diagnostic object graph.
// Allocation failure is terminal before listening or servo activity. No filesystem access or
// provisioning; caller must provide exclusive bus ownership and reviewed policy.
#pragma once
#include <new>
#include "controller_startup_config.h"
#include "startup_listener_owner.h"
#include "evidence_store.h"
#include "start_socket_session.h"
#include "start_listener.h"
namespace rocell_diag {
template<class Library,class Clock,class Server,class Client,class Socket,class Converter,class Crypto>
class ConfiguredStartupRuntime {
  using Store=EvidenceStore<16,2304>;
  using Owner=StartupListenerOwner<Library,Clock,Store,Converter,Crypto>;
  using Connection=StartSocketSession<Owner,Clock,Socket>;
  using Listener=StartListener<Server,Client,Connection,Owner,Clock>;
  struct Inner {
    Store store;Converter converter;Crypto crypto;Server server;Client client;Socket socket;
    Owner owner;Connection connection;Listener listener;
    Inner(Library& bus,Clock& clock,const ControllerStartupConfig& c,
        const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
        uint64_t issued,uint64_t expires,bool (*fault)(void*),void* context)
      :converter({c.normal.minimum_rad,c.normal.maximum_rad,c.normal.maximum_speed,c.normal.maximum_acceleration}),
       server(c.normal.port,1),socket(client),
       owner(bus,clock,store,converter,crypto,key,boot,nonce,issued,expires,c.normal.conversion,
             c.normal.policy_id,c.startup,c.reviewed_mode,c.normal.whole,fault,context),
       connection(owner,clock,socket),listener(server,client,connection,owner,clock,expires){}
    ~Inner(){server.end();client.stop();}
  };
 public:
  ConfiguredStartupRuntime()=default;
  ~ConfiguredStartupRuntime(){delete inner_;}
  ConfiguredStartupRuntime(const ConfiguredStartupRuntime&)=delete;
  ConfiguredStartupRuntime& operator=(const ConfiguredStartupRuntime&)=delete;
  bool initialize(Library& bus,Clock& clock,const char* policy,size_t length,const char* conversion,
      const DiagnosticKeyMaterial& material,const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
      bool (*fault)(void*),void* context){
    if(used_)return false;used_=true;
    static const char hex[]="0123456789abcdef";
    for(size_t i=0;i<16;++i){instance_[i*2]=hex[boot[i]>>4];instance_[i*2+1]=hex[boot[i]&15];}
    if(!parser_.parse(policy,length,conversion))return fail("STARTUP_CONFIGURATION_REJECTED");
    if(!fault||fault(context))return fail("OWNER_FAULT");
    const auto& config=*parser_.get();const uint64_t issued=clock.now_us();
    if(issued>INT64_MAX||config.normal.challenge_lifetime_us>static_cast<uint64_t>(INT64_MAX)-issued)
      return fail("INVALID_CLOCK");
    uint8_t key[32]={};if(!material.copy_to(key))return fail("KEY_NOT_LOADED");
    issued_=issued;expires_=issued+config.normal.challenge_lifetime_us;
    inner_=new(std::nothrow) Inner(bus,clock,config,key,boot,nonce,issued_,expires_,fault,context);
    volatile uint8_t* wipe=key;for(size_t i=0;i<32;++i)wipe[i]=0;
    if(!inner_)return fail("STARTUP_MEMORY_UNAVAILABLE");
    if(!inner_->listener.begin())return fail(inner_->listener.reason());
    return true;
  }
  void poll(){if(inner_&&!failure_)inner_->listener.poll();}
  bool exclusive_work()const{return inner_&&inner_->listener.state()==ListenerState::Running;}
  SessionState state()const{return failure_?SessionState::Fault:inner_?inner_->owner.state():SessionState::Idle;}
  const char* reason()const{return failure_?failure_:inner_?inner_->owner.reason():"NOT_CONFIGURED";}
  void configuration_failed(){used_=true;fail("CONFIGURATION_LOAD_FAILED");}
  void interference(){if(inner_)inner_->owner.interference();else fail("INTERFERING_COMMAND");}
  void export_failed(){if(inner_)inner_->owner.export_failed();else fail("EVIDENCE_FAILURE");}
  size_t size()const{return inner_?inner_->store.size():0;}
  bool faulted()const{return inner_&&inner_->store.faulted();}
  const typename Store::Record* get(size_t index)const{return inner_?inner_->store.get(index):nullptr;}
  const char* instance()const{return instance_;}
  uint64_t issued_us()const{return issued_;}uint64_t expires_us()const{return expires_;}
 private:
  bool fail(const char* reason){if(!failure_)failure_=reason;return false;}
  bool used_=false;const char* failure_=nullptr;char instance_[33]={};
  uint64_t issued_=0,expires_=0;ControllerStartupConfigParser parser_;
  Inner* inner_=nullptr;
};
}
