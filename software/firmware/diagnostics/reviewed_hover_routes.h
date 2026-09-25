// Offline authenticated-route prototype. Never register with a raw WebServer.
#pragma once
#include "reviewed_hover_owner.h"
#include "reviewed_hover_live_admission.h"
#include "reviewed_hover_recovery_admission.h"
#include <cstdio>
#include <cstring>
#include <type_traits>

namespace rocell_diag {
template<class Crypto,class Services,class Clock,class AuthWeb,
         bool SimulationOnly=false,bool Recovery=false>
class ReviewedHoverRoutes {
 public:
  static_assert(!SimulationOnly || Services::simulation_only,
                "Offline reviewed-hover selector requires simulation-only services");
  static_assert(!Recovery || !SimulationOnly,
                "Recovery is a distinct live-only fixed admission");
  using Owner=std::conditional_t<Recovery,
      ReviewedHoverOwnerT<ReviewedHoverRecoveryPolicy>,ReviewedHoverOwner>;
  ReviewedHoverRoutes(Crypto& crypto,Services& services,Clock& clock,AuthWeb& web,
                      const uint8_t (&boot)[16])
      :crypto_(crypto),services_(services),clock_(clock),web_(web){
    std::memcpy(boot_,boot,16);
  }
  void register_routes(){
    if(registered_)return;registered_=true;
    web_.on(Recovery?"/rocell/recovery-hover/start":"/rocell/reviewed-hover/start",
            HTTP_POST,[this](){start();});
    web_.on(Recovery?"/rocell/recovery-hover/status":"/rocell/reviewed-hover/status",
            HTTP_GET,[this](){status();});
    web_.on(Recovery?"/rocell/recovery-hover/record":"/rocell/reviewed-hover/record",
            HTTP_GET,[this](){record();});
    web_.on(Recovery?"/rocell/recovery-hover/receipt":"/rocell/reviewed-hover/receipt",
            HTTP_POST,[this](){receipt();});
    web_.on(Recovery?"/rocell/recovery-hover/next":"/rocell/reviewed-hover/next",
            HTTP_POST,[this](){next();});
  }
  void poll(){
    auto acquire=[this](ShoulderPreloadPose& p){return services_.reviewed_hover_sample(p);};
    auto write=[this](const uint16_t (&goals)[7],uint16_t speed,uint8_t acc){
      return services_.reviewed_hover_write(goals,speed,acc);};
    auto evidence=[this](const char* event,const ShoulderPreloadPose& p){
      return services_.reviewed_hover_evidence(event,p);};
    auto admitted=[this](){return services_.owned()&&services_.healthy();};
    owner_.poll(acquire,write,clock_,evidence,admitted);
  }
  bool claimed()const{return owner_.state()!=Owner::State::New;}
 private:
  static int nibble(char c){return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;}
  static bool parse_hex(const char* text,size_t size,uint8_t* out){
    for(size_t i=0;i<size;++i){int hi=nibble(text[2*i]),lo=nibble(text[2*i+1]);
      if(hi<0||lo<0)return false;out[i]=uint8_t(hi<<4|lo);}
    return true;
  }
  bool digest_matches(const uint8_t* ids,size_t count,const uint8_t* supplied){
    static const char* const names[6]={"A_CLEAR","A_HOVER","A_DOWN",
                                        "B_CLEAR","B_HOVER","B_DOWN"};
    static const char prefix[]="{\"acceleration\":1,\"export_before_next\":true,"
      "\"hardware_access\":false,\"maximum_writes\":16,"
      "\"motion_authorized\":false,\"one_use_per_boot\":true,\"pose_ids\":[";
    static const char suffix[]= "],\"schema\":\"rocell.reviewed_hover_manifest.v1\","
      "\"source_pose\":\"A_CLEAR\",\"speed\":20}";
    char canonical[640];size_t used=0;
    auto append=[&](const char* part){
      const size_t n=std::strlen(part);
      if(used+n>=sizeof(canonical))return false;
      std::memcpy(canonical+used,part,n);used+=n;return true;};
    if(!append(prefix))return false;
    for(size_t i=0;i<count;++i){
      if(ids[i]>=6||i&&!append(",")||!append("\"")||
         !append(names[ids[i]])||!append("\""))return false;
    }
    if(!append(suffix))return false;
    uint8_t calculated[32]{};
    if(!crypto_.sha256(reinterpret_cast<const uint8_t*>(canonical),used,calculated))return false;
    uint8_t difference=0;
    for(unsigned i=0;i<32;++i)difference|=calculated[i]^supplied[i];
    return difference==0;
  }
  bool request_ok(){
    if(web_.authenticated())return true;
    web_.send(403,"text/plain","");return false;
  }
  bool empty(){return web_.args()==0;}
  bool one_plain(){return web_.args()==1&&web_.argName(0)=="plain";}
  void start(){
    if(!request_ok())return;
    const auto body=web_.arg("plain");
    uint8_t count=0,ids[ReviewedHoverManifest::max_legs]{},digest[32]{};
    if constexpr(Recovery){
      uint8_t expected_release[32]{};
      if(!services_.reviewed_hover_release_digest(expected_release)){
        web_.send(409,"text/plain","LIVE_RELEASE_UNAVAILABLE");return;
      }
      ReviewedHoverRecoveryAdmission admission;
      if(!one_plain()||!ReviewedHoverRecoveryAdmission::parse(
          body.c_str(),body.length(),boot_,expected_release,crypto_,admission)){
        web_.send(400,"text/plain","");return;
      }
      count=ReviewedHoverRecoveryPolicy::legs;
      std::memcpy(ids,ReviewedHoverRecoveryPolicy::poses,count);
      std::memcpy(digest,admission.recipe_digest,32);
    }else if constexpr(SimulationOnly){
      // RCHM1 is explicitly offline and accepted only with simulation services.
      if(!one_plain()||body.length()<6+2+1+2+1+64||
         body.compare(0,6,"RCHM1:")!=0||body[8]!=':'){
        web_.send(400,"text/plain","");return;
      }
      uint8_t count_byte[1]={};
      if(!parse_hex(body.c_str()+6,1,count_byte)||!count_byte[0]||
         count_byte[0]>ReviewedHoverManifest::max_legs||
         body.length()!=6+2+1+2*count_byte[0]+1+64||
         body[9+2*count_byte[0]]!=':'){
        web_.send(400,"text/plain","");return;
      }
      count=count_byte[0];
      if(!parse_hex(body.c_str()+9,count,ids)||
         !parse_hex(body.c_str()+10+2*count,32,digest)||
         !ReviewedHoverManifest::validate(ids,count)||
         !digest_matches(ids,count,digest)){
        web_.send(400,"text/plain","");return;
      }
    }else{
      // Release identity comes from the image's trusted services, never from
      // the request itself. The current board adapter deliberately fails here.
      uint8_t expected_release[32]{};
      if(!services_.reviewed_hover_release_digest(expected_release)){
        web_.send(409,"text/plain","LIVE_RELEASE_UNAVAILABLE");return;
      }
      ReviewedHoverLiveAdmission admission;
      auto recipe_matches=[this](const uint8_t* selected,size_t size,const uint8_t* hash){
        return digest_matches(selected,size,hash);};
      if(!one_plain()||!ReviewedHoverLiveAdmission::parse(body.c_str(),body.length(),
             boot_,expected_release,recipe_matches,admission)){
        web_.send(400,"text/plain","");return;
      }
      count=admission.count;
      std::memcpy(ids,admission.pose_ids,count);
      std::memcpy(digest,admission.recipe_digest,32);
    }
    if(!services_.healthy()||!services_.memory_fits(sizeof(*this),16384)||
       !owner_.configure(ids,count,boot_,digest)){
      web_.send(409,"text/plain","");return;
    }
    auto reserve=[this](){return services_.reserve();};
    const bool ok=owner_.begin(reserve,clock_);
    web_.send(ok?202:409,"text/plain",ok?"CAPTURING_START":owner_.reason());
  }
  void status(){
    if(!request_ok())return;
    if(!empty()){web_.send(400,"text/plain","");return;}
    char response[128];std::snprintf(response,sizeof(response),"%s|%u",
      owner_.state()==Owner::State::AwaitExport?"AWAITING_EXPORT":owner_.reason(),owner_.leg());
    web_.send(200,"text/plain",response);
  }
  void record(){
    if(!request_ok())return;
    if(!empty()){web_.send(400,"text/plain","");return;}
    auto hash=[this](const uint8_t* data,size_t size,uint8_t (&digest)[32]){
      return crypto_.sha256(data,size,digest);};
    if(owner_.seal_record(record_,sizeof(record_),hash)!=sizeof(record_)||
       !crypto_.sha256(record_,sizeof(record_),digest_)){
      web_.send(409,"text/plain","");return;
    }
    static const char digits[]="0123456789abcdef";
    for(size_t i=0;i<sizeof(record_);++i){
      hex_[2*i]=digits[record_[i]>>4];hex_[2*i+1]=digits[record_[i]&15];}
    hex_[2*sizeof(record_)]=0;record_served_=true;
    web_.send(200,"text/plain",hex_);
  }
  void receipt(){
    if(!request_ok())return;
    const auto body=web_.arg("plain");char prefix[5];
    std::snprintf(prefix,sizeof(prefix),"%u:",owner_.leg());
    const size_t offset=std::strlen(prefix);
    if(!one_plain()||!record_served_||body.length()!=offset+64||
       std::strncmp(body.c_str(),prefix,offset)){
      web_.send(409,"text/plain","");return;
    }
    uint8_t supplied[32]{};
    if(!parse_hex(body.c_str()+offset,32,supplied)){
      web_.send(400,"text/plain","");return;
    }
    if(!services_.owned()||!services_.healthy()||
       std::memcmp(supplied,digest_,32)||
       !owner_.acknowledge(owner_.leg(),supplied,clock_)){
      web_.send(409,"text/plain","");return;
    }
    record_served_=false;
    char response[32];std::snprintf(response,sizeof(response),"READY|%u",owner_.leg());
    web_.send(200,"text/plain",
      owner_.state()==Owner::State::Complete?"COMPLETE":response);
  }
  void next(){
    if(!request_ok())return;
    const auto body=web_.arg("plain");char expected[4];
    std::snprintf(expected,sizeof(expected),"%u",owner_.leg());
    if(!one_plain()||body!=expected){web_.send(400,"text/plain","");return;}
    const bool ok=services_.owned()&&services_.healthy()&&
      owner_.begin_next(owner_.leg(),clock_);
    web_.send(ok?202:409,"text/plain",ok?"CAPTURING_START":owner_.reason());
  }
  Crypto& crypto_;Services& services_;Clock& clock_;AuthWeb& web_;
  Owner owner_;
  uint8_t boot_[16]{},record_[1163]{},digest_[32]{};
  char hex_[2327]{};
  bool registered_=false,record_served_=false;
};
}
