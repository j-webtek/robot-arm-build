// Uninstalled composition. Single control-task use only; no hardware access in
// construction/start. Every OTHER dispatcher must honor the shared reservation.
#pragma once
#include "shoulder_authorized_start.h"
#include "shoulder_export_receipt.h"
#include "shoulder_fault_settling_session.h"
#include <memory>
#include <new>
namespace rocell_diag {
template<class Crypto> class ShoulderSessionOwner {
 public:
  using Verifier=ShoulderReceiptVerifier<Crypto>;
  using Session=ShoulderPreloadSession<Crypto,Verifier>;
  using Settling=ShoulderFaultSettlingSession<Crypto,Session>;
  ShoulderSessionOwner(Crypto& crypto,ShoulderBusReservation& reservation,
      const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
      uint64_t issued,uint64_t expires,const char* command,ShoulderSessionScope approved,
      bool settling_authorized=false)
      :crypto_(crypto),reservation_(reservation),
       start_(key,boot,nonce,issued,expires,command,approved),
       verifier_(crypto,key,boot,command),session_(crypto,verifier_,boot_string(boot),command,approved){
    if(settling_authorized)settling_.reset(new(std::nothrow) Settling(crypto,session_,key,boot));
    ready_=!settling_authorized||bool(settling_);
  }
  ShoulderSessionOwner(const ShoulderSessionOwner&)=delete;
  ShoulderSessionOwner& operator=(const ShoulderSessionOwner&)=delete;
  const char* canonical_plan()const{return start_.canonical_plan();}
  const char* start_reason()const{return start_.reason();}
  Session* session(){return active_?&session_:nullptr;}
  Settling* settling(){return active_&&session_.phase()==ShoulderPreloadPhase::Fault?settling_.get():nullptr;}
  template<class Clock,class Admission>
  bool start(const uint8_t* token,size_t length,Clock& clock,Admission& admitted){
    if(!ready_)return false;
    auto activate=[this](const char*,const char*,ShoulderSessionScope){
      // Scope and identity were bound by the same constructor arguments.
      if(session_.phase()!=ShoulderPreloadPhase::Baseline)return false;
      active_=true;return true;
    };
    return start_.start(token,length,clock,crypto_,reservation_,admitted,activate);
  }
  template<class Bus,class Clock,class Admission>
  void advance(Bus& bus,Clock& clock,Admission& admitted){
    if(active_){
      session_.advance(bus,clock,admitted);
      if(auto* capture=settling())capture->advance(bus,clock,admitted);
    }
  }
 private:
  const char* boot_string(const uint8_t (&boot)[16]){
    static const char hex[]="0123456789abcdef";
    for(unsigned i=0;i<16;++i){boot_[2*i]=hex[boot[i]>>4];boot_[2*i+1]=hex[boot[i]&15];}
    return boot_;
  }
  Crypto& crypto_;ShoulderBusReservation& reservation_;
  char boot_[33]={};bool active_=false;
  ShoulderAuthorizedStart start_;Verifier verifier_;Session session_;
  std::unique_ptr<Settling> settling_;bool ready_=true;
};
}
