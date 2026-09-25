#define ROCELL_SIGNED_FIXTURE_ONLY
#include "test_reviewed_hover_signed_route.cpp"
#undef ROCELL_SIGNED_FIXTURE_ONLY

int main(int argc,char** argv){
  if(argc==2&&std::strcmp(argv[1],"--canonical")==0){
    std::fputs(ReviewedHoverRecoveryAdmission::canonical,stdout);
    return 0;
  }
  SigningCrypto crypto;Clock clock;Services services{clock};RawWeb web;
  services.live_release=true;
  const uint16_t positions[7]={2041,2094,2020,2620,2199,2041,2047};
  const uint16_t goals[7]={2047,2093,2021,2618,2197,2040,2047};
  for(unsigned i=0;i<7;++i){services.pos[i]=positions[i];services.goals[i]=goals[i];}
  uint8_t boot[16],key[32];for(auto& byte:boot)byte=0xab;
  for(unsigned i=0;i<32;++i)key[i]=uint8_t(i+1);
  ReviewedHoverComposition<SigningCrypto,Services,Clock,RawWeb,false,true> route(
      crypto,services,clock,web,key,boot);
  route.register_routes();route.register_routes();
  assert(web.collected==2&&web.routes.size()==5);
  for(const auto& item:web.routes)
    assert(item.first.find("/rocell/recovery-hover/")==0);
  constexpr const char* start="/rocell/recovery-hover/start";
  constexpr const char* status="/rocell/recovery-hover/status";
  uint8_t recipe[32]{};
  crypto.sha256(reinterpret_cast<const uint8_t*>(ReviewedHoverRecoveryAdmission::canonical),
      sizeof(ReviewedHoverRecoveryAdmission::canonical)-1,recipe);
  const char* digits="0123456789abcdef";
  auto hex=[&](const uint8_t* bytes,size_t count){
    std::string result;
    for(size_t i=0;i<count;++i){result+=digits[bytes[i]>>4];result+=digits[bytes[i]&15];}
    return result;
  };
  const std::string body="RCHR1:"+hex(boot,16)+":"+hex(recipe,32)+":"+
                         std::string(64,'c').replace(1,1,"d")+":LIVE_NONCONTACT";
  // Services returns 0xcd for each release byte, not 0xcc.
  uint8_t release[32];for(auto& byte:release)byte=0xcd;
  const std::string selector="RCHR1:"+hex(boot,16)+":"+hex(recipe,32)+":"+
                             hex(release,32)+":LIVE_NONCONTACT";
  assert(selector.size()==ReviewedHoverRecoveryAdmission::wire_size);
  auto signature=[&](const char* method,const char* path,const std::string& payload,
                     unsigned sequence){
    uint8_t hash[32],hmac[32],message[224]{};
    crypto.sha256(reinterpret_cast<const uint8_t*>(payload.data()),payload.size(),hash);
    size_t n=0;const char domain[]="RCCREQUEST01";
    for(char c:domain)message[n++]=uint8_t(c);
    for(auto byte:boot)message[n++]=byte;
    for(int shift=24;shift>=0;shift-=8)message[n++]=uint8_t(sequence>>shift);
    message[n++]=std::strcmp(method,"POST")==0;
    message[n++]=uint8_t(std::strlen(path));
    std::memcpy(message+n,path,std::strlen(path));n+=std::strlen(path);
    std::memcpy(message+n,hash,32);n+=32;
    crypto.hmac_sha256(key,message,n,hmac);
    return hex(hmac,32);
  };
  auto request=[&](const char* path,const std::string& payload,unsigned sequence,
                   bool signed_request,const char* signed_path=nullptr){
    web.body=payload;web.headers.clear();web.out.clear();
    if(signed_request){
      web.headers["X-Rocell-Sequence"]=std::to_string(sequence);
      web.headers["X-Rocell-Signature"]=signature(payload.empty()?"GET":"POST",
          signed_path?signed_path:path,payload,sequence);
    }
    web.routes.at(path)();
  };
  request(start,selector,0,false);assert(web.status==403&&!services.reserved);
  request(start,selector,0,true,status);assert(web.status==403&&!services.reserved);
  request(start,body,0,true);assert(web.status==400&&!services.reserved);
  std::string wrong_boot=selector;wrong_boot[6]='c';
  request(start,wrong_boot,1,true);assert(web.status==400&&!services.reserved);
  std::string wrong_recipe=selector;
  wrong_recipe[39]=wrong_recipe[39]=='0'?'1':'0';
  request(start,wrong_recipe,2,true);assert(web.status==400&&!services.reserved);
  request(start,selector,3,true);assert(web.status==202&&services.reserved&&
                                         services.writes==0);
  request(start,selector,3,true);assert(web.status==403&&services.writes==0);
  request(status,"",4,true);assert(web.status==200&&web.response=="CAPTURING_START|1");
  route.poll();assert(services.writes==0&&route.claimed());
  unsigned sequence=5;
  for(unsigned leg=1;leg<=5;++leg){
    for(unsigned n=0;n<20;++n){clock.now+=150000;route.poll();}
    request(status,"",sequence++,true);
    assert(web.status==200&&web.response=="AWAITING_EXPORT|"+std::to_string(leg));
    assert(services.writes==leg);
    request("/rocell/recovery-hover/record","",sequence++,true);
    assert(web.status==200&&web.response.size()==2326);
    uint8_t record[1163]{},digest[32]{};
    assert(ReviewedHoverLiveAdmission::hex(web.response.c_str(),1163,record));
    assert(record[58]==leg&&record[59]==ReviewedHoverRecoveryPolicy::poses[leg-1]);
    crypto.sha256(record,sizeof(record),digest);
    request("/rocell/recovery-hover/receipt",std::to_string(leg)+":"+hex(digest,32),
            sequence++,true);
    assert(web.status==200);
    assert(web.response==(leg==5?"COMPLETE":"READY|"+std::to_string(leg+1)));
    if(leg<5){
      request("/rocell/recovery-hover/next",std::to_string(leg+1),sequence++,true);
      assert(web.status==202&&web.response=="CAPTURING_START");
    }
  }
  assert(services.writes==5);
  request("/rocell/recovery-hover/next","5",sequence++,true);
  assert(web.status==409&&services.writes==5);
  return 0;
}
