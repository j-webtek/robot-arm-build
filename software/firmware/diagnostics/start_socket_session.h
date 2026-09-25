// One accepted connection, one bounded request, one best-effort reply. Socket
// adapters MUST provide nonblocking receive/send_once (-2 = would-block,
// -1 = error, 0 receive = EOF). No listener or automatic reconstruction/retry.
#pragma once
#include <cstdio>
#include "start_http_request.h"
namespace rocell_diag {
template<class Owner,class Clock,class Socket>
class StartSocketSession {
 public:
  StartSocketSession(Owner& owner,Clock& clock,Socket& socket)
      :owner_(owner),clock_(clock),socket_(socket),request_(owner) {}
  bool begin(){
    if(used_)return false;used_=true;
    active_=request_.begin(clock_.now_us());
    if(!active_){reason_=request_.reason();socket_.close();}
    return active_;
  }
  bool poll(){
    if(!active_)return false;
    if(!request_.poll(clock_.now_us()))return finish_reply(false,request_.reason());
    // One bounded read per poll lets the controller service other work.
    const int n=socket_.receive(input_,sizeof(input_));
    const uint64_t now=clock_.now_us();
    if(n>0){
      if(static_cast<size_t>(n)>sizeof(input_) || !request_.feed(input_,static_cast<size_t>(n),now)){
        request_.abort();return finish_reply(false,"REQUEST_REJECTED");
      }
      return true; // Drain already-available extra bytes before committing.
    }
    if(n==-2){
      if(!request_.poll(now))return finish_reply(false,request_.reason());
      if(!request_.ready())return true;
      const bool accepted=request_.finish(now);
      return finish_reply(accepted,request_.reason());
    }
    request_.abort();return finish_reply(false,n==0?"PEER_DISCONNECTED":"SOCKET_READ_FAILED");
  }
  bool active() const{return active_;}
  const char* reason() const{return reason_;}
 private:
  bool finish_reply(bool accepted,const char* reason){
    active_=false;reason_=reason;
    // This acknowledges local admission only, never arrival or host receipt.
    const char* body=accepted?"{\"accepted\":true,\"retry_allowed\":false}":
                              "{\"accepted\":false,\"retry_allowed\":false}";
    const int n=snprintf(reply_,sizeof(reply_),
        "HTTP/1.1 %s\r\nContent-Type: application/json\r\nContent-Length: %u\r\n"
        "Cache-Control: no-store\r\nConnection: close\r\n\r\n%s",
        accepted?"202 Accepted":"400 Bad Request",static_cast<unsigned>(strlen(body)),body);
    if(n<0 || static_cast<size_t>(n)>=sizeof(reply_) ||
       socket_.send_once(reinterpret_cast<const uint8_t*>(reply_),static_cast<size_t>(n))!=n){
      owner_.interference();reason_="RESPONSE_UNCERTAIN";
    }
    socket_.close();return false;
  }
  Owner& owner_;Clock& clock_;Socket& socket_;StartHttpRequest<Owner> request_;
  bool used_=false,active_=false;const char* reason_="NOT_STARTED";
  uint8_t input_[512]={};char reply_[256]={};
};
}
