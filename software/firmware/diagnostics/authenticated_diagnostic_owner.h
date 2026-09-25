// Single-lifetime owner for the authenticated v3 pipeline. Keep this and its
// referenced bus/clock/sink/converter/crypto in static or other long-lived storage.
// No route, provisioning, restart, or automatic retry is provided here.
#pragma once
#include "authorized_start.h"
#include "admitted_session.h"
namespace rocell_diag {
template<class Library,class Clock,class Sink,class Converter,class Crypto>
class AuthenticatedDiagnosticOwner {
 public:
  AuthenticatedDiagnosticOwner(Library& library,Clock& clock,Sink& sink,Converter& converter,Crypto& crypto,
      const uint8_t (&key)[32],const uint8_t (&boot)[16],const uint8_t (&nonce)[32],
      uint64_t issued,uint64_t expires,const char* conversion,const WholeArmBaselinePolicy& policy,
      bool (*external_fault)(void*),void* context)
      :clock_(clock),sink_(sink),converter_(converter),crypto_(crypto),
       external_fault_(external_fault),context_(context),
       authorization_(key,boot,nonce,issued,expires,conversion,&policy),
       session_(library,clock,sink,converter,policy,expires,&fault_callback,this) {}
  AuthenticatedDiagnosticOwner(const AuthenticatedDiagnosticOwner&)=delete;
  AuthenticatedDiagnosticOwner& operator=(const AuthenticatedDiagnosticOwner&)=delete;

  bool start(const uint8_t* token,size_t length) {
    if(attempted_)return false;
    attempted_=true; // Admission failures cannot reopen the owner.
    if(faulted()){latch(sink_.faulted()?"EVIDENCE_FAILURE":"OWNER_FAULT");return false;}
    const bool ok=authorization_.start(token,length,clock_,crypto_,converter_,sink_,session_,session_);
    if(!ok)latch(session_.state()==SessionState::Fault?session_.reason():authorization_.reason());
    return ok;
  }
  bool sample() {
    // Polling an idle or terminal owner must never acquire more bus data.
    if(state()!=SessionState::Sampling)return false;
    if(faulted()){latch(sink_.faulted()?"EVIDENCE_FAILURE":"OWNER_FAULT");return false;}
    return session_.sample();
  }
  void interference(){latch("INTERFERING_COMMAND");}
  void export_failed(){latch("EVIDENCE_FAILURE");}
  SessionState state() const{return failure_?SessionState::Fault:session_.state();}
  const char* reason() const{return failure_?failure_:session_.reason();}
  bool owned() const{return attempted_ || failure_;}
 private:
  bool faulted() const {
    return failure_ || sink_.faulted() || !external_fault_ || external_fault_(context_);
  }
  static bool fault_callback(void* context){
    return static_cast<AuthenticatedDiagnosticOwner*>(context)->faulted();
  }
  void latch(const char* reason){if(!failure_)failure_=reason;}
  Clock& clock_;Sink& sink_;Converter& converter_;Crypto& crypto_;
  bool (*external_fault_)(void*);void* context_;
  bool attempted_=false;const char* failure_=nullptr;
  AuthorizedStart authorization_;
  AdmittedSession<Library,Clock,Sink,Converter> session_;
};
}
