#define main route_fixture_main
#include "test_reviewed_hover_routes.cpp"
#undef main
#include "reviewed_hover_composition.h"

struct SigningCrypto : Crypto {
  bool hmac_sha256(const uint8_t* key,const uint8_t* bytes,size_t count,uint8_t (&out)[32]){
    sha256(bytes,count,out);
    for(unsigned i=0;i<32;++i)out[i]^=key[i];
    return true;
  }
};
struct RawWeb {
  std::map<std::string,std::function<void()>> routes,unused;
  std::map<std::string,std::string> headers,out;
  std::string body,response;int status=0;unsigned collected=0;
  void collectHeaders(const char**,size_t size){collected=unsigned(size);}
  template<class Handler>void on(const char* path,int,Handler handler){routes[path]=handler;}
  int args(){return body.empty()?0:1;}
  std::string argName(int){return "plain";}
  std::string arg(const char*){return body;}
  std::string header(const char* name){return headers[name];}
  void sendHeader(const char* name,const char* value){out[name]=value;}
  void send(int code,const char*,const char* value){status=code;response=value;}
};
#ifndef ROCELL_SIGNED_FIXTURE_ONLY
int main(){
  SigningCrypto crypto;Clock clock;Services services{clock};RawWeb raw;
  uint8_t boot[16],key[32];for(auto& b:boot)b=0xab;
  for(unsigned i=0;i<32;++i)key[i]=uint8_t(i+1);
  ReviewedHoverComposition<SigningCrypto,Services,Clock,RawWeb,true> composition(
      crypto,services,clock,raw,key,boot);
  composition.register_routes();composition.register_routes();
  assert(raw.collected==2&&raw.routes.size()==5);
  for(const auto& route:raw.routes)
    assert(route.first.find("/rocell/reviewed-hover/")==0);
  const char* path="/rocell/reviewed-hover/start";
  const std::string canonical="{\"acceleration\":1,\"export_before_next\":true,"
    "\"hardware_access\":false,\"maximum_writes\":16,\"motion_authorized\":false,"
    "\"one_use_per_boot\":true,\"pose_ids\":[\"A_HOVER\"],"
    "\"schema\":\"rocell.reviewed_hover_manifest.v1\","
    "\"source_pose\":\"A_CLEAR\",\"speed\":20}";
  uint8_t manifest_digest[32]{};
  crypto.sha256(reinterpret_cast<const uint8_t*>(canonical.data()),canonical.size(),manifest_digest);
  const char* digits="0123456789abcdef";std::string selector="RCHM1:01:01:";
  for(auto b:manifest_digest){selector+=digits[b>>4];selector+=digits[b&15];}
  auto signature=[&](const char* method,const char* exact_path,const std::string& body,unsigned sequence){
    uint8_t hash[32],hmac[32],message[224]{};
    crypto.sha256(reinterpret_cast<const uint8_t*>(body.data()),body.size(),hash);
    size_t n=0;const char domain[]="RCCREQUEST01";
    for(char c:domain)message[n++]=uint8_t(c);
    for(auto b:boot)message[n++]=b;
    for(int shift=24;shift>=0;shift-=8)message[n++]=uint8_t(sequence>>shift);
    message[n++]=std::strcmp(method,"POST")==0;message[n++]=uint8_t(std::strlen(exact_path));
    std::memcpy(message+n,exact_path,std::strlen(exact_path));n+=std::strlen(exact_path);
    std::memcpy(message+n,hash,32);n+=32;
    crypto.hmac_sha256(key,message,n,hmac);
    std::string hex;for(auto b:hmac){hex+=digits[b>>4];hex+=digits[b&15];}
    return hex;
  };
  auto request=[&](const char* action,const std::string& body,unsigned sequence,
                   bool sign,const char* signed_path=nullptr){
    const std::string exact=std::string("/rocell/reviewed-hover/")+action;
    raw.body=body;raw.headers.clear();raw.out.clear();
    if(sign){raw.headers["X-Rocell-Sequence"]=std::to_string(sequence);
      raw.headers["X-Rocell-Signature"]=signature(body.empty()?"GET":"POST",
          signed_path?signed_path:exact.c_str(),body,sequence);}
    raw.routes.at(exact)();
  };
  request("start",selector,0,false);assert(raw.status==403&&!services.reserved);
  request("start",selector,0,true,"/rocell/reviewed-hover/next");
  assert(raw.status==403&&!services.reserved);
  request("start",selector,0,true);assert(raw.status==202&&services.reserved);
  assert(raw.out.count("X-Rocell-Signature")&&raw.out.at("X-Rocell-Sequence")=="0");
  request("start",selector,0,true);assert(raw.status==403);
  request("status","",1,true);assert(raw.status==200&&raw.response=="CAPTURING_START|1");
  request("status","",1,true);assert(raw.status==403);
  composition.poll();assert(services.writes==0&&composition.claimed());
  Services live_services{clock};live_services.live_release=true;
  RawWeb live_raw;
  ReviewedHoverComposition<SigningCrypto,Services,Clock,RawWeb> live_composition(
      crypto,live_services,clock,live_raw,key,boot);
  live_composition.register_routes();
  std::string live_selector="RCHL2:"+std::string(32,'a');
  for(unsigned i=0;i<16;++i)live_selector[6+2*i+1]='b';
  live_selector+=":01:01:";
  for(auto b:manifest_digest){live_selector+=digits[b>>4];live_selector+=digits[b&15];}
  live_selector+=':'+std::string(64,'c');
  for(unsigned i=0;i<32;++i)live_selector[110+2*i+1]='d';
  live_selector+=":LIVE_NONCONTACT";
  live_raw.body=selector;
  live_raw.routes.at(path)();assert(live_raw.status==403&&!live_services.reserved);
  live_raw.body=live_selector;
  live_raw.headers["X-Rocell-Sequence"]="0";
  live_raw.headers["X-Rocell-Signature"]=signature("POST",path,live_selector,0);
  live_raw.routes.at(path)();assert(live_raw.status==202&&live_services.reserved&&
                                   live_services.writes==0);
  live_raw.routes.at(path)();assert(live_raw.status==403&&live_services.writes==0);
  return 0;
}
#endif
