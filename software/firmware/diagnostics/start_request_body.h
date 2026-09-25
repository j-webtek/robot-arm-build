// Bounded, single-use body receiver for a future owner-only ingress. The transport
// must reject ambiguous HTTP framing before begin(), feed decoded body bytes only,
// and report disconnects via abort(). No HTTP server or live route is enabled here.
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
namespace rocell_diag {
template<class Owner>
class StartRequestBody {
 public:
  static constexpr size_t MinimumBytes=sizeof("rocell.diagnostic-start.v1")+64+2+1+32;
  static constexpr size_t MaximumBytes=sizeof("rocell.diagnostic-start.v1")+64+2+16384+32;
  explicit StartRequestBody(Owner& owner):owner_(owner) {}
  ~StartRequestBody(){erase();}
  StartRequestBody(const StartRequestBody&)=delete;
  StartRequestBody& operator=(const StartRequestBody&)=delete;
  bool begin(size_t length,uint64_t now,uint64_t budget_us) {
    if(used_)return false;
    used_=true;
    if(owner_.owned() || length<MinimumBytes || length>MaximumBytes || !budget_us ||
       budget_us>3000000 || now>INT64_MAX || budget_us>static_cast<uint64_t>(INT64_MAX)-now)
      return fail("INVALID_REQUEST_BODY");
    expected_=length;last_=now;deadline_=now+budget_us;receiving_=true;return true;
  }
  bool append(const uint8_t* bytes,size_t length,uint64_t now) {
    if(!receiving_)return false;
    if(!timely(now))return fail("BODY_TIMEOUT_OR_CLOCK");
    if(!bytes || !length || length>expected_-received_)return fail("BODY_LENGTH_MISMATCH");
    memcpy(body_+received_,bytes,length);received_+=length;return true;
  }
  bool finish(uint64_t now) {
    if(!receiving_)return false;
    if(!timely(now))return fail("BODY_TIMEOUT_OR_CLOCK");
    if(received_!=expected_)return fail("BODY_LENGTH_MISMATCH");
    receiving_=false; // Consume before entering the synchronous command owner.
    const bool started=owner_.start(body_,received_);
    reason_=started?"STARTED":"OWNER_REJECTED";
    erase();return started;
  }
  void abort(){if(receiving_)fail("BODY_DISCONNECTED");}
  const char* reason() const{return reason_;}
 private:
  bool timely(uint64_t now){
    if(now<last_ || now>=deadline_)return false;
    last_=now;return true;
  }
  bool fail(const char* reason){
    receiving_=false;reason_=reason;owner_.interference();erase();return false;
  }
  void erase(){
    // Do not retain a usable signed token in diagnostics after a terminal attempt.
    volatile uint8_t* bytes=body_;
    for(size_t i=0;i<received_;++i)bytes[i]=0;
    received_=0;
  }
  Owner& owner_;bool used_=false,receiving_=false;
  size_t expected_=0,received_=0;uint64_t last_=0,deadline_=0;
  const char* reason_="NOT_STARTED";
  uint8_t body_[MaximumBytes]={}; // Static/long-lived storage, never callback stack.
};
}
