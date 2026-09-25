#include <cassert>
#include <cstdint>
#include <functional>
#include <map>
#include <string>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "reviewed_hover_routes.h"
using namespace rocell_diag;
struct Clock {uint64_t now=900000;uint64_t now_us(){return now;}};
struct Crypto {
  bool sha256(const uint8_t* bytes,size_t count,uint8_t (&out)[32]){
    for(unsigned i=0;i<32;++i)out[i]=uint8_t(i);
    for(size_t i=0;i<count;++i)out[i%32]^=bytes[i];return true;
  }
};
struct Services {
  static constexpr bool simulation_only=true;
  Clock& clock;bool reserved=false,live_release=false;unsigned writes=0;
  uint8_t pinned_recipe[32]{};
  uint16_t pos[7]={2040,2082,2033,2609,2233,2041,2047};
  uint16_t goals[7]={2047,2075,2039,2600,2233,2040,2047};
  const int residual[7]={0,1,-1,1,2,1,0};
  bool reserve(){if(reserved)return false;return reserved=true;}
  bool owned(){return reserved;}bool healthy(){return true;}
  bool memory_fits(size_t,size_t){return true;}
  bool reviewed_hover_release_digest(uint8_t (&digest)[32]){
    if(!live_release)return false;
    for(auto& byte:digest)byte=0xcd;
    return true;
  }
  bool reviewed_hover_recipe_digest(uint8_t (&digest)[32]){
    for(unsigned i=0;i<32;++i)digest[i]=pinned_recipe[i];
    return true;
  }
  bool reviewed_hover_evidence(const char*,const ShoulderPreloadPose&){return true;}
  bool reviewed_hover_write(const uint16_t (&target)[7],uint16_t speed,uint8_t acc){
    assert(speed==20&&acc==1&&writes<16);
    for(int i=0;i<7;++i){
      if(goals[i]!=target[i])pos[i]=uint16_t(int(target[i])+residual[i]);
      goals[i]=target[i];
    }
    ++writes;return true;
  }
  bool reviewed_hover_sample(ShoulderPreloadPose& p){
    p={};p.started_us=clock.now-50000;p.finished_us=clock.now;
    for(int i=0;i<7;++i){p.goal[i]=goals[i];p.position[i]=pos[i];p.torque[i]=1;
      p.feedback[i][0]=uint8_t(pos[i]);p.feedback[i][1]=uint8_t(pos[i]>>8);}
    return true;
  }
};
struct Web {
  std::map<std::string,std::function<void()>> routes;
  bool signed_request=true;std::string body,response;int status=0;
  template<class Handler>void on(const char* path,int,Handler handler){routes[path]=handler;}
  bool authenticated(){return signed_request;}
  int args(){return body.empty()?0:1;}
  std::string argName(int){return "plain";}
  std::string arg(const char*){return body;}
  void send(int code,const char*,const char* text){status=code;response=text;}
};
int main(){
  Crypto crypto;Clock clock;Services services{clock};Web web;uint8_t boot[16];
  for(auto& byte:boot)byte=0xab;
  ReviewedHoverRoutes<Crypto,Services,Clock,Web,true> routes(crypto,services,clock,web,boot);
  routes.register_routes();routes.register_routes();assert(web.routes.size()==5);
  auto request=[&](const char* action,std::string body=""){
    web.body=body;web.routes[std::string("/rocell/reviewed-hover/")+action]();
  };
  const uint8_t ids[16]={1,2,1,0,4,5,4,3,1,2,1,0,4,5,4,3};
  const char* digits="0123456789abcdef";
  std::string selector="RCHM1:10:";
  for(auto id:ids){selector+=digits[id>>4];selector+=digits[id&15];}
  const std::string canonical="{\"acceleration\":1,\"export_before_next\":true,"
    "\"hardware_access\":false,\"maximum_writes\":16,\"motion_authorized\":false,"
    "\"one_use_per_boot\":true,\"pose_ids\":[\"A_HOVER\",\"A_DOWN\",\"A_HOVER\","
    "\"A_CLEAR\",\"B_HOVER\",\"B_DOWN\",\"B_HOVER\",\"B_CLEAR\","
    "\"A_HOVER\",\"A_DOWN\",\"A_HOVER\",\"A_CLEAR\",\"B_HOVER\",\"B_DOWN\","
    "\"B_HOVER\",\"B_CLEAR\"],\"schema\":\"rocell.reviewed_hover_manifest.v1\","
    "\"source_pose\":\"A_CLEAR\",\"speed\":20}";
  uint8_t manifest_digest[32]{};
  crypto.sha256(reinterpret_cast<const uint8_t*>(canonical.data()),canonical.size(),manifest_digest);
  selector+=':';for(auto byte:manifest_digest){selector+=digits[byte>>4];selector+=digits[byte&15];}
  // Default/production route cannot turn an explicitly offline selector into
  // movement, even if the request is otherwise authenticated and well formed.
  Services production_services{clock};Web production_web;
  for(unsigned i=0;i<32;++i)production_services.pinned_recipe[i]=manifest_digest[i];
  ReviewedHoverRoutes<Crypto,Services,Clock,Web> production(
      crypto,production_services,clock,production_web,boot);
  production.register_routes();production_web.body=selector;
  production_web.routes.at("/rocell/reviewed-hover/start")();
  assert(production_web.status==409&&!production_services.reserved&&
         production_services.writes==0&&production_services.pos[0]==2040);
  production_web.body="RCHL2:"+selector;
  production_web.routes.at("/rocell/reviewed-hover/start")();
  assert(production_web.status==409&&!production_services.reserved&&
         production_services.writes==0);
  production_services.live_release=true;
  production_web.body=selector;
  production_web.routes.at("/rocell/reviewed-hover/start")();
  assert(production_web.status==400&&!production_services.reserved);
  production_web.body="RCHL2:"+std::string(32,'a');
  for(unsigned i=0;i<16;++i)production_web.body[6+2*i+1]='b';
  production_web.body+=":10:";
  for(auto id:ids){production_web.body+=digits[id>>4];production_web.body+=digits[id&15];}
  production_web.body+=':';
  for(auto byte:manifest_digest){production_web.body+=digits[byte>>4];
    production_web.body+=digits[byte&15];}
  production_web.body+=':'+std::string(64,'c');
  const size_t release_at=108+2*16;
  for(unsigned i=0;i<32;++i)production_web.body[release_at+2*i+1]='d';
  production_web.body+=":LIVE_NONCONTACT";
  auto live_selector=production_web.body;
  auto reject_live=[&](std::string candidate){
    production_web.body=candidate;
    production_web.routes.at("/rocell/reviewed-hover/start")();
    assert(production_web.status==400&&!production_services.reserved&&
           production_services.writes==0);
  };
  auto wrong_boot=live_selector;wrong_boot[6]='0';reject_live(wrong_boot);
  auto wrong_recipe=live_selector;wrong_recipe[43+2*16]='0';reject_live(wrong_recipe);
  auto wrong_release=live_selector;wrong_release[release_at]='0';reject_live(wrong_release);
  auto wrong_mode=live_selector;wrong_mode.replace(wrong_mode.size()-15,15,"LIVE_CONTACT");
  reject_live(wrong_mode);
  // A distinct but valid one-leg recipe must be rejected by the release pin,
  // before reserve or any servo write.
  std::string other_canonical=canonical;
  const auto names_at=other_canonical.find("\"pose_ids\":[");
  const auto names_end=other_canonical.find(']',names_at);
  assert(names_at!=std::string::npos&&names_end!=std::string::npos);
  other_canonical.replace(names_at+12,names_end-(names_at+12),"\"A_HOVER\"");
  uint8_t other_digest[32]{};
  crypto.sha256(reinterpret_cast<const uint8_t*>(other_canonical.data()),
                other_canonical.size(),other_digest);
  std::string other_selector="RCHL2:"+std::string(32,'a');
  for(unsigned i=0;i<16;++i)other_selector[6+2*i+1]='b';
  other_selector+=":01:01:";
  for(auto byte:other_digest){other_selector+=digits[byte>>4];other_selector+=digits[byte&15];}
  other_selector+=':'+std::string(64,'c');
  const size_t other_release_at=108+2;
  for(unsigned i=0;i<32;++i)other_selector[other_release_at+2*i+1]='d';
  other_selector+=":LIVE_NONCONTACT";
  production_web.body=other_selector;
  production_web.routes.at("/rocell/reviewed-hover/start")();
  assert(production_web.status==409&&production_web.response=="RECIPE_NOT_RELEASED"&&
         !production_services.reserved&&production_services.writes==0);
  production_web.body=live_selector;
  production_web.routes.at("/rocell/reviewed-hover/start")();
  assert(production_web.status==202&&production_services.reserved&&
         production_services.writes==0);
  production_web.body=live_selector;
  production_web.routes.at("/rocell/reviewed-hover/start")();
  assert(production_web.status==409&&production_services.writes==0);
  web.signed_request=false;
  request("start",selector);assert(web.status==403&&!services.reserved);
  request("status");assert(web.status==403);
  web.signed_request=true;
  request("start","RCHM1:00:00:"+std::string(64,'0'));
  assert(web.status==400&&!services.reserved);
  request("start",selector.substr(0,selector.size()-1));
  assert(web.status==400&&!services.reserved);
  std::string mismatched=selector;mismatched[mismatched.size()-1]='0';
  if(mismatched==selector)mismatched[mismatched.size()-1]='1';
  request("start",mismatched);assert(web.status==400&&!services.reserved);
  request("next","1");assert(web.status!=202&&!services.reserved);
  request("start",selector);assert(web.status==202&&services.reserved);
  request("start",selector);assert(web.status==409);
  for(unsigned leg=1;leg<=16;++leg){
    for(unsigned n=0;n<7;++n){clock.now+=150000;routes.poll();}
    assert(services.writes==leg);
    request("status");assert(web.response=="AWAITING_EXPORT|"+std::to_string(leg));
    request("receipt",std::to_string(leg)+":"+std::string(64,'0'));
    assert(web.status==409);
    request("record");assert(web.status==200&&web.response.size()==2326);
    auto encoded=web.response;uint8_t raw[1163],digest[32];
    for(size_t i=0;i<1163;++i)raw[i]=uint8_t(std::stoul(encoded.substr(2*i,2),nullptr,16));
    assert(raw[58]==leg&&raw[59]==ids[leg-1]);
    crypto.sha256(raw,sizeof(raw),digest);
    std::string receipt=std::to_string(leg)+":";
    for(auto byte:digest){receipt+=digits[byte>>4];receipt+=digits[byte&15];}
    web.signed_request=false;
    request("receipt",receipt);assert(web.status==403);
    web.signed_request=true;
    request("receipt",std::to_string(leg)+":"+std::string(64,'0'));
    assert(web.status==409);
    request("receipt",receipt);assert(web.status==200);
    assert(web.response==(leg==16?"COMPLETE":"READY|"+std::to_string(leg+1)));
    routes.poll();assert(services.writes==leg);
    request("receipt",receipt);assert(web.status==409);
    if(leg<16){
      request("next",std::to_string(leg));assert(web.status==400);
      request("next",std::to_string(leg+1));assert(web.status==202);
      request("next",std::to_string(leg+1));assert(web.status==409);
    }
  }
  request("start",selector);assert(web.status==409);
  routes.poll();assert(services.writes==16);
  return 0;
}
