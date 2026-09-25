// Adapt asynchronous startup preparation to the existing single-use listener.
// Sampling here means exclusive work (preparation OR post-write acquisition).
#pragma once
#include <utility>
#include "startup_authenticated_owner.h"
namespace rocell_diag {
template<class Library,class Clock,class Sink,class Converter,class Crypto>
class StartupListenerOwner {
  using Core=StartupAuthenticatedOwner<Library,Clock,Sink,Converter,Crypto>;
 public:
  template<class... Args> explicit StartupListenerOwner(Args&&... args):core_(std::forward<Args>(args)...){}
  bool start(const uint8_t* token,size_t length){if(used_)return false;used_=true;return core_.start(token,length);}
  bool sample(){core_.poll();return state()!=SessionState::Fault;}
  bool owned()const{return used_||core_.state()!=StartupOwnerState::Idle;}
  SessionState state()const{
    switch(core_.state()){
      case StartupOwnerState::Idle:return SessionState::Idle;
      case StartupOwnerState::Captured:return SessionState::Captured;
      case StartupOwnerState::Fault:return SessionState::Fault;
      default:return SessionState::Sampling;
    }
  }
  const char* reason()const{return core_.reason();}
  void interference(){core_.interference();}
  void export_failed(){core_.export_failed();}
 private:
  Core core_;bool used_=false;
};
}
