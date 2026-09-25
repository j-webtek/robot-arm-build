// Authenticated prepare/status adapters; reviewed bounds are copied at startup,
// never accepted from HTTP. Actual acquisition is performed only by polling.
#pragma once
#include <cstdio>
#include <cstring>
#include <cstdint>
namespace rocell_diag {
template<class Controller,class Auth,class Web> class CharacterizationPrepareRoutes {
 public:
  CharacterizationPrepareRoutes(Controller& controller,Auth& auth,Web& web,
                                 const uint16_t (&bounds)[7][2])
      :controller_(controller),auth_(auth),web_(web){memcpy(bounds_,bounds,sizeof(bounds_));}
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/characterization/prepare",HTTP_POST,[this](){
      if(!admit())return;
      bool ok=controller_.prepare(bounds_);
      web_.send(ok?202:409,"application/json",ok?"{\"capture_scheduled\":true,\"movement_performed\":false}":"{\"capture_scheduled\":false}");
    });
    web_.on("/rocell/characterization/status",HTTP_GET,[this](){
      if(!admit())return;
      auto* s=controller_.session();
      int n=snprintf(response_,sizeof(response_),
        "{\"schema\":\"rocell.characterization_status.v1\",\"state\":\"%s\",\"completed\":%u,\"writes_attempted\":%u}",
        controller_.state_name(),s?s->completed():0,s?s->writes():0);
      if(n<0||size_t(n)>=sizeof(response_)){web_.send(500,"application/json","{}");return;}
      web_.send(200,"application/json",response_);
    });
    web_.on("/rocell/characterization/challenge",HTTP_GET,[this](){
      if(!admit())return;
      uint8_t bytes[224];size_t size=controller_.publish_challenge(bytes,sizeof(bytes));
      if(!size||size>sizeof(bytes)){web_.send(409,"text/plain","");return;}
      const char* hex="0123456789abcdef";
      for(size_t i=0;i<size;++i){response_[2*i]=hex[bytes[i]>>4];response_[2*i+1]=hex[bytes[i]&15];}
      response_[2*size]=0;web_.send(200,"text/plain",response_);
    });
    web_.on("/rocell/characterization/reference",HTTP_GET,[this](){
      if(!admit())return;
      uint8_t bytes[468];size_t size=controller_.publish_reference(bytes,sizeof(bytes));
      if(size!=sizeof(bytes)){web_.send(409,"text/plain","");return;}
      const char* hex="0123456789abcdef";
      for(size_t i=0;i<size;++i){response_[2*i]=hex[bytes[i]>>4];response_[2*i+1]=hex[bytes[i]&15];}
      response_[2*size]=0;web_.send(200,"text/plain",response_);
    });
  }
 private:
  bool admit(){
    web_.sendHeader("Cache-Control","no-store");
    if(!auth_()){web_.send(403,"application/json","{}");return false;}
    if(web_.args()){web_.send(400,"application/json","{}");return false;}
    return true;
  }
  Controller& controller_;Auth& auth_;Web& web_;uint16_t bounds_[7][2];
  bool registered_=false;char response_[937]={};
};
}
