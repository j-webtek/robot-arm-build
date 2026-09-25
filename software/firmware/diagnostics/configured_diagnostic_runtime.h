// Place this runtime in static storage. Initialization consumes one attempt and
// constructs its complete object graph only after local policy/key validation.
// No filesystem access, key generation, listener re-arm or firmware deployment.
#pragma once
#include <new>
#include <type_traits>
#include "controller_diagnostic_config.h"
#include "authenticated_diagnostic_owner.h"
#include "evidence_store.h"
#include "start_socket_session.h"
#include "start_listener.h"
#include "diagnostic_status_json.h"
namespace rocell_diag {
template<class Library,class Clock,class Server,class Client,class Socket,class Converter,class Crypto>
class ConfiguredDiagnosticRuntime {
  using Store=EvidenceStore<16>;
  using Owner=AuthenticatedDiagnosticOwner<Library,Clock,Store,Converter,Crypto>;
  using Connection=StartSocketSession<Owner,Clock,Socket>;
  using Listener=StartListener<Server,Client,Connection,Owner,Clock>;
  struct Inner {
    Store store;Converter converter;Crypto crypto;Server server;Client client;Socket socket;
    Owner owner;Connection connection;Listener listener;
    Inner(Library& library,Clock& clock,const ControllerDiagnosticConfig& config,
        const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
        uint64_t issued,uint64_t expires,bool (*fault)(void*),void* context)
        :converter({config.minimum_rad,config.maximum_rad,config.maximum_speed,config.maximum_acceleration}),
         server(config.port,1),socket(client),
         owner(library,clock,store,converter,crypto,key,boot,nonce,issued,expires,config.conversion,config.whole,fault,context),
         connection(owner,clock,socket),listener(server,client,connection,owner,clock,expires) {}
    ~Inner(){server.end();client.stop();}
  };
 public:
  ConfiguredDiagnosticRuntime()=default;
  ~ConfiguredDiagnosticRuntime(){if(inner_)inner_->~Inner();}
  ConfiguredDiagnosticRuntime(const ConfiguredDiagnosticRuntime&)=delete;
  ConfiguredDiagnosticRuntime& operator=(const ConfiguredDiagnosticRuntime&)=delete;
  bool initialize(Library& library,Clock& clock,const char* policy,size_t length,const char* conversion,
      const DiagnosticKeyMaterial& material,const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
      bool (*fault)(void*),void* context){
    if(used_)return false;used_=true;
    static const char hex[]="0123456789abcdef";
    for(size_t i=0;i<16;++i){instance_[2*i]=hex[boot[i]>>4];instance_[2*i+1]=hex[boot[i]&15];}
    if(!parser_.parse(policy,length,conversion))return fail("CONFIGURATION_REJECTED");
    const auto& config=*parser_.get();
    if(!fault || fault(context))return fail("OWNER_FAULT");
    const uint64_t issued=clock.now_us();
    if(issued>INT64_MAX || config.challenge_lifetime_us>static_cast<uint64_t>(INT64_MAX)-issued)
      return fail("INVALID_CLOCK");
    uint8_t key[32]={};
    if(!material.copy_to(key))return fail("KEY_NOT_LOADED");
    issued_=issued;expires_=issued+config.challenge_lifetime_us;
    inner_=new(&storage_) Inner(library,clock,config,key,boot,nonce,issued_,expires_,fault,context);
    volatile uint8_t* wipe=key;for(size_t i=0;i<32;++i)wipe[i]=0;
    if(!inner_->listener.begin())return fail(inner_->listener.reason());
    return true;
  }
  void poll(){if(inner_ && !failure_)inner_->listener.poll();}
  bool exclusive_work() const{return inner_ && inner_->listener.state()==ListenerState::Running;}
  void configuration_failed(){fail("CONFIGURATION_LOAD_FAILED");used_=true;}
  SessionState state() const{return failure_?SessionState::Fault:inner_?inner_->owner.state():SessionState::Idle;}
  const char* reason() const{return failure_?failure_:inner_?inner_->owner.reason():"NOT_CONFIGURED";}
  void interference(){if(inner_)inner_->owner.interference();else fail("INTERFERING_COMMAND");}
  void export_failed(){if(inner_)inner_->owner.export_failed();else fail("EVIDENCE_FAILURE");}
  size_t size() const{return inner_?inner_->store.size():0;}
  bool faulted() const{return inner_ && inner_->store.faulted();}
  const typename Store::Record* get(size_t index) const{return inner_?inner_->store.get(index):nullptr;}
  const char* instance() const{return instance_;}
  uint64_t issued_us() const{return issued_;}
  uint64_t expires_us() const{return expires_;}
 private:
  bool fail(const char* reason){if(!failure_)failure_=reason;return false;}
  bool used_=false;const char* failure_=nullptr;char instance_[33]={};
  uint64_t issued_=0,expires_=0;
  ControllerDiagnosticConfigParser parser_;
  typename std::aligned_storage<sizeof(Inner),alignof(Inner)>::type storage_;
  Inner* inner_=nullptr;
};
}
