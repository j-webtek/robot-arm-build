// Single-listener orchestration. All referenced objects must have the same
// long-lived owner. No default port, keys, policy or automatic re-arm is supplied.
#pragma once
#include "diagnostic_session.h"
namespace rocell_diag {
enum class ListenerState { Idle, Listening, Running, Finished, Fault };
template<class Server,class Client,class Connection,class Owner,class Clock>
class StartListener {
 public:
  StartListener(Server& server,Client& client,Connection& connection,Owner& owner,Clock& clock,uint64_t expires)
      :server_(server),client_(client),connection_(connection),owner_(owner),clock_(clock),expires_(expires) {}
  StartListener(const StartListener&)=delete;
  StartListener& operator=(const StartListener&)=delete;
  bool begin(){
    if(used_)return false;used_=true;
    last_=clock_.now_us();
    if(owner_.owned() || last_>=expires_ || expires_>INT64_MAX)return fail("LISTENER_NOT_ADMITTED");
    server_.begin();
    if(!static_cast<bool>(server_))return fail("LISTENER_START_FAILED");
    state_=ListenerState::Listening;reason_="LISTENING";return true;
  }
  void poll(){
    if(state_==ListenerState::Listening){
      const uint64_t now=clock_.now_us();
      if(now<last_ || now>=expires_){fail("CHALLENGE_EXPIRED_OR_CLOCK");return;}
      last_=now;
      if(owner_.owned()){fail("OWNER_ALREADY_CONSUMED");return;}
      Client incoming=server_.accept();
      if(incoming.fd()<0)return;
      client_=incoming;
      // Retire listener before reading or dispatching the first request. A
      // connection timeout is terminal, not an invitation to accept another.
      server_.end();
      if(!connection_.begin()){fail("CONNECTION_NOT_ADMITTED");return;}
      state_=ListenerState::Running;reason_="REQUEST_ACTIVE";
    }
    if(state_!=ListenerState::Running)return;
    if(connection_.active()){connection_.poll();return;}
    if(owner_.state()==SessionState::Sampling)owner_.sample();
    if(owner_.state()==SessionState::Captured){state_=ListenerState::Finished;reason_="CAPTURED";}
    else if(owner_.state()==SessionState::Fault){state_=ListenerState::Fault;reason_=owner_.reason();}
  }
  ListenerState state() const{return state_;}
  const char* reason() const{return reason_;}
 private:
  bool fail(const char* reason){
    reason_=reason;state_=ListenerState::Fault;owner_.interference();server_.end();client_.stop();return false;
  }
  Server& server_;Client& client_;Connection& connection_;Owner& owner_;Clock& clock_;
  uint64_t expires_,last_=0;bool used_=false;
  ListenerState state_=ListenerState::Idle;const char* reason_="NOT_STARTED";
};
}
