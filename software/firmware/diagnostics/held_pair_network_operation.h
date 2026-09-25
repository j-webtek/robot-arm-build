// One explicit network operation. No default port, key, challenge or rearm.
// Allocate off-stack; runtime/operation/clock outlive this object. Destroy a
// finished initial network before constructing the separately admitted return.
#pragma once
#include "held_pair_listener_owner.h"
#include "start_socket_session.h"
#include "start_listener.h"
namespace rocell_diag {
template<class Runtime,class Operation,class Clock,class Server,class Client,class Socket>
class HeldPairNetworkOperation {
 public:
  using Owner=HeldPairListenerOwner<Runtime,Operation>;
  using Connection=StartSocketSession<Owner,Clock,Socket>;
  using Listener=StartListener<Server,Client,Connection,Owner,Clock>;
  HeldPairNetworkOperation(Runtime& runtime,Operation& operation,Clock& clock,
      uint16_t port,uint64_t expires,bool returning)
      :runtime_(runtime),port_(port),returning_(returning),server_(port,1),socket_(client_),
       owner_(runtime,operation,returning),connection_(owner_,clock,socket_),
       listener_(server_,client_,connection_,owner_,clock,expires){}
  HeldPairNetworkOperation(const HeldPairNetworkOperation&)=delete;
  HeldPairNetworkOperation& operator=(const HeldPairNetworkOperation&)=delete;
  ~HeldPairNetworkOperation(){server_.end();client_.stop();}
  bool begin(){
    if(used_)return false;used_=true;
    const auto expected=returning_?HeldPairPhase::AwaitingExport:HeldPairPhase::New;
    if(port_<1024||runtime_.phase()!=expected){owner_.interference();failed_=true;return false;}
    if(!listener_.begin()){failed_=true;return false;}return true;
  }
  void poll(){if(used_&&!failed_)listener_.poll();}
  ListenerState state()const{return failed_?ListenerState::Fault:listener_.state();}
  bool exclusive_work()const{return state()==ListenerState::Listening||state()==ListenerState::Running;}
  const char* reason()const{return failed_?"PAIR_NETWORK_ADMISSION_FAILED":listener_.reason();}
 private:
  Runtime& runtime_;uint16_t port_;bool returning_,used_=false,failed_=false;
  Server server_;Client client_;Socket socket_;Owner owner_;Connection connection_;Listener listener_;
};
}
