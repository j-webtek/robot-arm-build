// Fixed-target, authenticated-web-compatible return route. Registration is
// inert; this file is not yet included in the deployed composition.
#pragma once
#include "park_reanchor_owner.h"
#include <cstdio>
#include <cstring>

namespace rocell_diag {
template<class Crypto,class Services,class Clock,class Web> class ParkReanchorRoutes {
 public:
  ParkReanchorRoutes(Crypto& crypto,Services& services,Clock& clock,Web& web,
      const uint8_t (&boot)[16]):crypto_(crypto),services_(services),clock_(clock),web_(web){
    memcpy(boot_,boot,16);
  }
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/park-return/start",HTTP_POST,[this](){start();});
    web_.on("/rocell/park-return/status",HTTP_GET,[this](){status();});
    web_.on("/rocell/park-return/record",HTTP_GET,[this](){record();});
    web_.on("/rocell/park-return/receipt",HTTP_POST,[this](){receipt();});
  }
  void poll(){
    auto acquire=[this](ShoulderPreloadPose& pose){return services_.park_return_sample(pose);};
    auto write=[this](uint8_t a,uint8_t b,uint16_t x,uint16_t y,uint16_t speed,uint8_t acc){
      return services_.park_return_write(a,b,x,y,speed,acc);
    };
    auto evidence=[this](const char* event,const ShoulderPreloadPose& pose){
      return services_.park_return_evidence(event,pose);
    };
    auto admitted=[this](){return services_.owned()&&services_.healthy();};
    owner_.poll(acquire,write,clock_,evidence,admitted);
  }
  bool claimed()const{return owner_.state()!=ParkReanchorOwner::State::New;}
 private:
  static int nibble(char c){
    return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
  }
  bool empty(){return web_.args()==0;}
  void start(){
    if(!empty()){web_.send(400,"text/plain","");return;}
    auto reserve=[this](){return services_.reserve();};
    const bool ok=owner_.begin(reserve,clock_);
    web_.send(ok?202:409,"text/plain",ok?"CAPTURING_START":owner_.reason());
  }
  void status(){
    if(!empty()){web_.send(400,"text/plain","");return;}
    char response[128];
    snprintf(response,sizeof(response),"%s|%u",owner_.reason(),owner_.writes());
    web_.send(200,"text/plain",response);
  }
  bool capture(){
    size_=owner_.copy_result(boot_,record_,sizeof(record_));
    if(size_!=sizeof(record_)||!crypto_.sha256(record_,size_,digest_))return false;
    static const char digits[]="0123456789abcdef";
    for(size_t i=0;i<size_;++i){
      hex_[2*i]=digits[record_[i]>>4];hex_[2*i+1]=digits[record_[i]&15];
    }
    hex_[2*size_]=0;return true;
  }
  void record(){
    if(!empty()){web_.send(400,"text/plain","");return;}
    if(!capture()){web_.send(409,"text/plain","");return;}
    web_.send(200,"text/plain",hex_);
  }
  void receipt(){
    const auto body=web_.arg("plain");
    if(web_.args()!=1||web_.argName(0)!="plain"||body.length()!=64||
       owner_.state()!=ParkReanchorOwner::State::AwaitExport||!capture()){
      web_.send(409,"text/plain","");return;
    }
    uint8_t difference=0;
    for(unsigned i=0;i<32;++i){
      const int hi=nibble(body[2*i]),lo=nibble(body[2*i+1]);
      if(hi<0||lo<0){web_.send(400,"text/plain","");return;}
      difference|=uint8_t((hi<<4|lo)^digest_[i]);
    }
    if(difference||!owner_.mark_export_verified(true)){
      web_.send(409,"text/plain","");return;
    }
    web_.send(200,"text/plain","RETURN_RECORDED");
  }
  Crypto& crypto_;Services& services_;Clock& clock_;Web& web_;
  ParkReanchorOwner owner_;
  uint8_t boot_[16]={},record_[ParkReanchorOwner::record_size]={},digest_[32]={};
  char hex_[2*ParkReanchorOwner::record_size+1]={};
  size_t size_=0;bool registered_=false;
};
}
