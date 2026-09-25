// Receipt -> admitted conversion -> one write -> timed acquisition. No network
// ingress is enabled here. Converter MUST perform reviewed admission and return
// the actual target without writing to the servo bus.
#pragma once
#include "diagnostic_receipt.h"
#include "diagnostic_session.h"
namespace rocell_diag {
class ReceivedSession {
 public:
  ReceivedSession():used_(false),reason_(nullptr) {}
  template<class Library,class Clock,class Sink,class Converter>
  bool start(Library& library,Clock& clock,Sink& sink,Converter& converter,
      const char* boot,const char* command,const char* payload,size_t length,
      uint16_t samples,uint64_t pair_budget,uint64_t interval_us=1000000,WriteBoundaryGuard guard={}) {
    if(used_){fail("DUPLICATE_START");return false;}
    used_=true;
    if(!samples || samples>2000 || !pair_budget || pair_budget>interval_us ||
       interval_us<1000 || interval_us>60000000){fail("INVALID_INPUT");return false;}
    if(!receipt_.accept(boot,command,payload,length,clock.now_us())){
      fail("RECEIPT_REJECTED");return false;
    }
    // Account for receipt in addition to the session's four boundary records.
    if(!sink.reserve(static_cast<size_t>(samples)+5) ||
       !receipt_.encode(buffer_,sizeof(buffer_)) || !sink.publish("receipt",buffer_)){
      fail("EVIDENCE_FAILURE");return false;
    }
    uint16_t target=0;
    if(!converter.admit_and_convert(receipt_.received_radians(),receipt_.speed(),
                                   receipt_.acceleration(),target)){
      fail("ADMISSION_REJECTED");return false;
    }
    // Elbow joint 3 -> servo 14 is pinned reference mapping, not caller input.
    return session_.start(library,clock,sink,receipt_.boot_id(),receipt_.command_id(),14,target,receipt_.speed(),
                          receipt_.acceleration(),samples,pair_budget,interval_us,guard);
  }
  template<class Library,class Clock,class Sink>
  bool sample(Library& library,Clock& clock,Sink& sink){return session_.sample(library,clock,sink);}
  void interference(){fail("INTERFERING_COMMAND");}
  void export_failed(){fail("EVIDENCE_FAILURE");}
  SessionState state() const{return session_.state();}
  const char* reason() const{return reason_?reason_:session_.reason();}
 private:
  void fail(const char* reason){if(!reason_)reason_=reason;session_.interference();}
  bool used_;const char* reason_;
  DiagnosticReceipt receipt_;
  DiagnosticSession session_;
  char buffer_[2048];
};
}
