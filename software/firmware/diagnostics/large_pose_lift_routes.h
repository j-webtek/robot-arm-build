// Authenticated exact P0 -> T1 route. The literal body "T1" selects the only
// compiled movement; callers cannot supply servo IDs or target positions.
#pragma once
#include "large_pose_lift_owner.h"
#include <cstring>
#include <cstdio>
namespace rocell_diag {
template<class Crypto,class Services,class Clock,class Web> class LargePoseLiftRoutes {
 public:
  LargePoseLiftRoutes(Crypto& crypto,Services& services,Clock& clock,Web& web,
      const uint8_t (&boot)[16]):crypto_(crypto),services_(services),clock_(clock),web_(web){
    memcpy(boot_,boot,16);
  }
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/large-pose-lift/start",HTTP_POST,[this](){start();});
    web_.on("/rocell/large-pose-lift/status",HTTP_GET,[this](){status();});
    web_.on("/rocell/large-pose-lift/record",HTTP_GET,[this](){record();});
    web_.on("/rocell/large-pose-lift/receipt",HTTP_POST,[this](){receipt();});
  }
  void poll(){
    auto acquire=[this](ShoulderPreloadPose& pose){return services_.large_pose_lift_sample(pose);};
    auto write=[this](uint8_t a,uint8_t b,uint8_t c,uint16_t x,uint16_t y,uint16_t z,
                      uint16_t speed,uint8_t acc){
      return services_.large_pose_lift_write(a,b,c,x,y,z,speed,acc);};
    auto evidence=[this](const char* event,const ShoulderPreloadPose& pose){
      return services_.large_pose_lift_evidence(event,pose);};
    auto admitted=[this](){return services_.owned()&&services_.healthy();};
    owner_.poll(acquire,write,clock_,evidence,admitted);
  }
  bool claimed()const{return owner_.state()!=LargePoseLiftOwner::State::New;}
 private:
  static int nibble(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
  bool empty(){return web_.args()==0;}
  void start(){
    const auto body=web_.arg("plain");
    if(web_.args()!=1||web_.argName(0)!="plain"||body!="T1"){
      web_.send(400,"text/plain","");return;
    }
    auto reserve=[this](){return services_.reserve();};
    const bool ok=owner_.begin(reserve,clock_);
    web_.send(ok?202:409,"text/plain",ok?"CAPTURING_START":owner_.reason());
  }
  void status(){
    if(!empty()){web_.send(400,"text/plain","");return;}
    char response[128];snprintf(response,sizeof(response),"%s|%u",owner_.reason(),owner_.writes());
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
    for(unsigned i=0;i<32;++i){const int hi=nibble(body[2*i]),lo=nibble(body[2*i+1]);
      if(hi<0||lo<0){web_.send(400,"text/plain","");return;}
      difference|=uint8_t((hi<<4|lo)^digest_[i]);}
    if(difference||!owner_.mark_export_verified(true)){
      web_.send(409,"text/plain","");return;
    }
    web_.send(200,"text/plain","LARGE_POSE_T1_RECORDED");
  }
  Crypto& crypto_;Services& services_;Clock& clock_;Web& web_;LargePoseLiftOwner owner_;
  uint8_t boot_[16]={},record_[1133]={},digest_[32]={};char hex_[2267]={};
  size_t size_=0;bool registered_=false;
};
}
