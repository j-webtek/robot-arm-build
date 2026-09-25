// Authenticated fixed sixteen-leg P4 repeat routes. No caller-supplied targets.
#pragma once
#include "p4_midpoint_owner.h"
#include <cstring>
#include <cstdio>
namespace rocell_diag {
template<class Crypto,class Services,class Clock,class Web> class P4MidpointRoutes {
 public:
  P4MidpointRoutes(Crypto& crypto,Services& services,Clock& clock,Web& web,
      const uint8_t (&boot)[16]):crypto_(crypto),services_(services),clock_(clock),web_(web){
    memcpy(boot_,boot,16);
  }
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/p4-midpoint/start",HTTP_POST,[this](){start();});
    web_.on("/rocell/p4-midpoint/status",HTTP_GET,[this](){status();});
    web_.on("/rocell/p4-midpoint/record",HTTP_GET,[this](){record();});
    web_.on("/rocell/p4-midpoint/receipt",HTTP_POST,[this](){receipt();});
    web_.on("/rocell/p4-midpoint/next",HTTP_POST,[this](){next();});
  }
  void poll(){
    auto acquire=[this](ShoulderPreloadPose& pose){return services_.large_pose_relief_sample(pose);};
    auto write=[this](uint8_t a,uint16_t x,
                      uint16_t speed,uint8_t acc){
      return services_.large_pose_relief_write(a,x,speed,acc);};
    auto evidence=[this](const char* event,const ShoulderPreloadPose& pose){
      return services_.large_pose_relief_evidence(event,pose);};
    auto admitted=[this](){return services_.owned()&&services_.healthy();};
    owner_.poll(acquire,write,clock_,evidence,admitted);
  }
  bool claimed()const{return owner_.state()!=P4MidpointOwner::State::New;}
 private:
  static int nibble(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
  bool empty(){return web_.args()==0;}
  void start(){
    const auto body=web_.arg("plain");
    if(web_.args()!=1||web_.argName(0)!="plain"||body!="P4M16"){
      web_.send(400,"text/plain","");return;
    }
    auto reserve=[this](){return services_.memory_fits(sizeof(*this),16384)&&services_.reserve();};
    const bool ok=owner_.begin(reserve,clock_);
    web_.send(ok?202:409,"text/plain",ok?"CAPTURING_START":owner_.reason());
  }
  void status(){
    if(!empty()){web_.send(400,"text/plain","");return;}
    char response[128];snprintf(response,sizeof(response),"%s|%u",owner_.state()==P4MidpointOwner::State::AwaitExport?"AWAITING_EXPORT":owner_.reason(),owner_.leg());
    web_.send(200,"text/plain",response);
  }
  bool capture(){
    auto hash=[this](const uint8_t* data,size_t size,uint8_t (&digest)[32]){return crypto_.sha256(data,size,digest);};
    size_=owner_.seal_record(boot_,record_,sizeof(record_),hash);
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
  void next(){
    const auto body=web_.arg("plain");char expected[4];
    snprintf(expected,sizeof(expected),"%u",owner_.leg());
    if(web_.args()!=1||web_.argName(0)!="plain"||body!=expected){
      web_.send(400,"text/plain","");return;
    }
    const bool ok=services_.owned()&&services_.healthy()&&owner_.begin_next(owner_.leg(),clock_);
    web_.send(ok?202:409,"text/plain",ok?"CAPTURING_START":owner_.reason());
  }
  void receipt(){
    const auto body=web_.arg("plain");char prefix[5];
    snprintf(prefix,sizeof(prefix),"%u:",owner_.leg());const size_t offset=strlen(prefix);
    if(web_.args()!=1||web_.argName(0)!="plain"||body.length()!=offset+64||
       std::strncmp(body.c_str(),prefix,offset)||!capture()){
      web_.send(409,"text/plain","");return;
    }
    uint8_t supplied[32];
    for(unsigned i=0;i<32;++i){const int hi=nibble(body[offset+2*i]),lo=nibble(body[offset+2*i+1]);
      if(hi<0||lo<0){web_.send(400,"text/plain","");return;}
      supplied[i]=uint8_t(hi<<4|lo);
    }
    if(!services_.owned()||!services_.healthy()||!owner_.acknowledge(owner_.leg(),supplied,clock_)){
      web_.send(409,"text/plain","");return;
    }
    char response[32];snprintf(response,sizeof(response),"READY|%u",owner_.leg());
    web_.send(200,"text/plain",owner_.state()==P4MidpointOwner::State::Complete?"COMPLETE":response);
  }
  Crypto& crypto_;Services& services_;Clock& clock_;Web& web_;P4MidpointOwner owner_;
  uint8_t boot_[16]={},record_[1130]={},digest_[32]={};char hex_[2261]={};
  size_t size_=0;bool registered_=false;
};
}
