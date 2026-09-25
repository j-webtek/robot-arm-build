// Restricted HTTP/1.1 framing for one diagnostic start, independent of sockets.
// Feed raw bytes before any unbounded server parsing; poll deadlines even when
// idle. Only finish after the full request is buffered. Close the connection
// after any terminal outcome; never parse a pipelined second request.
#pragma once
#include "start_request_body.h"
namespace rocell_diag {
template<class Owner>
class StartHttpRequest {
 public:
  explicit StartHttpRequest(Owner& owner):owner_(owner),body_(owner) {}
  bool begin(uint64_t now,uint64_t budget_us=3000000) {
    if(used_)return false;
    used_=true;
    if(owner_.owned() || !budget_us || budget_us>3000000 || now>INT64_MAX ||
       budget_us>static_cast<uint64_t>(INT64_MAX)-now)return fail("INVALID_HTTP_REQUEST");
    last_=now;deadline_=now+budget_us;active_=true;return true;
  }
  bool poll(uint64_t now) {
    if(!active_)return false;
    if(now<last_ || now>=deadline_)return fail("HTTP_TIMEOUT_OR_CLOCK");
    last_=now;return true;
  }
  bool feed(const uint8_t* bytes,size_t length,uint64_t now) {
    if(!poll(now))return false;
    if(!bytes || !length)return fail("INVALID_HTTP_BYTES");
    size_t offset=0;
    while(!header_done_ && offset<length){
      const uint8_t c=bytes[offset++];
      if(header_size_==sizeof(header_)-1 || (c<32 && c!='\r' && c!='\n') || c>126)
        return fail("INVALID_HTTP_HEADERS");
      header_[header_size_++]=static_cast<char>(c);header_[header_size_]=0;
      if(header_size_>=4 && !memcmp(header_+header_size_-4,"\r\n\r\n",4)){
        if(!parse_headers() || !body_.begin(expected_,now,deadline_-now))return fail("INVALID_HTTP_HEADERS");
        header_done_=true;
      }
    }
    if(offset<length){
      const size_t count=length-offset;
      if(count>expected_-received_)return fail("HTTP_BODY_LENGTH_MISMATCH");
      if(!body_.append(bytes+offset,count,now))return fail("HTTP_BODY_REJECTED");
      received_+=count;
    }
    return true;
  }
  bool ready() const{return active_ && header_done_ && received_==expected_;}
  bool finish(uint64_t now){
    if(!poll(now))return false;
    if(!ready())return fail("INCOMPLETE_HTTP_REQUEST");
    active_=false;
    const bool ok=body_.finish(now);reason_=ok?"STARTED":"OWNER_REJECTED";return ok;
  }
  void abort(){if(active_)fail("HTTP_DISCONNECTED");}
  const char* reason() const{return reason_;}
 private:
  bool fail(const char* reason){
    active_=false;reason_=reason;body_.abort();owner_.interference();return false;
  }
  bool parse_headers(){
    char* line=header_;char* end=strstr(line,"\r\n");
    if(!end)return false;*end=0;
    if(strcmp(line,"POST /rocell/diagnostics/start HTTP/1.1"))return false;
    line=end+2;unsigned seen=0;
    while(*line){
      end=strstr(line,"\r\n");if(!end)return false;
      if(end==line)return seen==15 && end+2==header_+header_size_;
      *end=0;
      char* colon=strchr(line,':');if(!colon || colon==line || colon[1]!=' ')return false;
      *colon=0;const char* value=colon+2;
      for(char* p=line;*p;++p){
        if(*p>='A' && *p<='Z')*p=static_cast<char>(*p-'A'+'a');
        if(!((*p>='a' && *p<='z') || *p=='-'))return false;
      }
      unsigned bit=0;
      if(!strcmp(line,"host")){
        bit=1;const size_t n=strlen(value);if(!n || n>128)return false;
        for(size_t i=0;i<n;++i){const char c=value[i];
          if(!((c>='0'&&c<='9')||(c>='a'&&c<='z')||(c>='A'&&c<='Z')||c=='.'||c==':'||c=='-'))return false;
        }
      }else if(!strcmp(line,"content-length")){
        bit=2;const size_t n=strlen(value);if(!n || n>5 || value[0]=='0')return false;
        size_t count=0;for(size_t i=0;i<n;++i){if(value[i]<'0'||value[i]>'9')return false;count=count*10+value[i]-'0';}
        if(count<StartRequestBody<Owner>::MinimumBytes || count>StartRequestBody<Owner>::MaximumBytes)return false;
        expected_=count;
      }else if(!strcmp(line,"content-type")){
        bit=4;if(strcmp(value,"application/octet-stream"))return false;
      }else if(!strcmp(line,"connection")){
        bit=8;if(strcmp(value,"close"))return false;
      }else return false; // Includes Transfer-Encoding, Expect and folded fields.
      if(seen&bit)return false;seen|=bit;line=end+2;
    }
    return false;
  }
  Owner& owner_;StartRequestBody<Owner> body_;
  bool used_=false,active_=false,header_done_=false;
  size_t header_size_=0,expected_=0,received_=0;uint64_t last_=0,deadline_=0;
  const char* reason_="NOT_STARTED";char header_[2048]={};
};
}
