// Signed-route adapter for a bounded shoulder park step. Route registration is
// inert; start accepts only two four-digit targets in the reviewed envelope.
#pragma once
#include "park_step_owner.h"
#include <cstring>
#include <cstdio>
namespace rocell_diag {
template<class Crypto,class Services,class Clock,class Web> class ParkStepRoutes {
 public:
  ParkStepRoutes(Crypto& crypto,Services& services,Clock& clock,Web& web,
      const uint8_t (&boot)[16]):crypto_(crypto),services_(services),clock_(clock),web_(web){
    memcpy(boot_,boot,16);
  }
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/park-step/start",HTTP_POST,[this](){start();});
    web_.on("/rocell/park-step/status",HTTP_GET,[this](){status();});
    web_.on("/rocell/park-step/record",HTTP_GET,[this](){record();});
    web_.on("/rocell/park-step/receipt",HTTP_POST,[this](){receipt();});
  }
  void poll(){
    auto acquire=[this](ShoulderPreloadPose& pose){return services_.park_step_sample(pose);};
    auto write=[this](uint8_t a,uint8_t b,uint16_t x,uint16_t y,uint16_t speed,uint8_t acc){
      return services_.park_step_write(a,b,x,y,speed,acc);
    };
    auto evidence=[this](const char* event,const ShoulderPreloadPose& pose){
      return services_.park_step_evidence(event,pose);
    };
    auto admitted=[this](){return services_.owned()&&services_.healthy();};
    owner_.poll(acquire,write,clock_,evidence,admitted);
  }
  bool claimed()const{return owner_.state()!=ParkStepOwner::State::New;}
 private:
  static int nibble(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
  static bool digit(char c){return c>='0'&&c<='9';}
  bool empty(){return web_.args()==0;}
  void start(){
    const auto body=web_.arg("plain");
    if(web_.args()!=1||web_.argName(0)!="plain"||body.length()!=9||body[4]!=','||
       !digit(body[0])||!digit(body[1])||!digit(body[2])||!digit(body[3])||
       !digit(body[5])||!digit(body[6])||!digit(body[7])||!digit(body[8])){
      web_.send(400,"text/plain","");return;
    }
    uint16_t first=0,second=0;
    for(unsigned i=0;i<4;++i){first=first*10+(body[i]-'0');second=second*10+(body[i+5]-'0');}
    const int progress=2389-int(first);
    if(progress<12||progress>48||progress%12||second!=1725+progress){
      web_.send(400,"text/plain","");return;
    }
    auto reserve=[this](){return services_.reserve();};
    const bool ok=owner_.begin(first,second,reserve,clock_);
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
    for(size_t i=0;i<size_;++i){hex_[2*i]=digits[record_[i]>>4];hex_[2*i+1]=digits[record_[i]&15];}
    hex_[2*size_]=0;return true;
  }
  void record(){
    if(!empty()){web_.send(400,"text/plain","");return;}
    if(!capture()){web_.send(409,"text/plain","");return;}
    web_.send(200,"text/plain",hex_);
  }
  void receipt(){
    const auto body=web_.arg("plain");
    if(web_.args()!=1||web_.argName(0)!="plain"||body.length()!=64||!capture()){
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
    web_.send(200,"text/plain","PARK_STEP_RECORDED");
  }
  Crypto& crypto_;Services& services_;Clock& clock_;Web& web_;
  ParkStepOwner owner_;
  uint8_t boot_[16]={},record_[1131]={},digest_[32]={};
  char hex_[2263]={};size_t size_=0;bool registered_=false;
};
}
