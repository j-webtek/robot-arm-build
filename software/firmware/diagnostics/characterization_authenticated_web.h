// Same-task WebServer facade: registered handlers only run after authentication;
// their responses are signed before forwarding. No bus/controller references.
#pragma once
#include "characterization_http_auth.h"
#include <cstdio>
namespace rocell_diag {
template<class Gate,class Web> class CharacterizationAuthenticatedWeb {
 public:
  CharacterizationAuthenticatedWeb(Gate& gate,Web& web):gate_(gate),web_(web){}
  void collect_headers(){
    const char* names[]={"X-Rocell-Sequence","X-Rocell-Signature"};
    web_.collectHeaders(names,2);
  }
  template<class Handler> void on(const char* path,int method,Handler handler){
    // Arduino WebServer requires HTTPMethod, while route facades accept int.
    // Preserve the platform's declared method type rather than relying on an
    // implicit int-to-enum conversion hidden by permissive desktop fakes.
    web_.on(path,static_cast<decltype(HTTP_GET)>(method),[this,path,method,handler](){
      active_=false;sent_=false;
      if(method!=HTTP_GET&&method!=HTTP_POST){web_.send(405,"text/plain","");return;}
      const auto body=web_.arg("plain");
      if(!authenticate_characterization_http(gate_,web_,method==HTTP_GET?"GET":"POST",path,
          reinterpret_cast<const uint8_t*>(body.c_str()),body.length(),sequence_)){
        web_.sendHeader("Cache-Control","no-store");web_.send(403,"text/plain","");return;
      }
      active_=true;handler();
      if(!sent_)send(500,"text/plain","");
      active_=false;
    });
  }
  bool authenticated()const{return active_&&!sent_;}
  int args(){return web_.args();}
  auto argName(int index){return web_.argName(index);}
  auto arg(const char* name){return web_.arg(name);}
  void sendHeader(const char* name,const char* value){web_.sendHeader(name,value);}
  void send(int status,const char* content_type,const char* raw){
    if(!active_||sent_)return;
    sent_=true;uint8_t signature[32];size_t size=raw?strlen(raw):0;
    if(!raw||!gate_.sign_response(sequence_,status,reinterpret_cast<const uint8_t*>(raw),size,signature)){
      web_.send(500,"text/plain","");return;
    }
    char sequence[11],hex[65]={};snprintf(sequence,sizeof(sequence),"%u",unsigned(sequence_));
    const char* digits="0123456789abcdef";
    for(unsigned i=0;i<32;++i){hex[2*i]=digits[signature[i]>>4];hex[2*i+1]=digits[signature[i]&15];}
    web_.sendHeader("X-Rocell-Sequence",sequence);web_.sendHeader("X-Rocell-Signature",hex);
    web_.sendHeader("Cache-Control","no-store");web_.send(status,content_type,raw);
  }
 private:
  Gate& gate_;Web& web_;uint32_t sequence_=0;bool active_=false,sent_=false;
};
}
