#include "shoulder_authorized_start.h"
#include <cassert>
#include <vector>
#include <string>
#include <iostream>
using namespace rocell_diag;
// Framing/ownership unit test only. Real HMAC interoperability is tested by
// the existing start-envelope suite; this stub is deliberately not security proof.
struct Crypto {bool hmac_sha256(const uint8_t*,const uint8_t*,size_t,uint8_t* out){memset(out,0,32);return true;}};
struct Clock {uint64_t time=10;uint64_t now_us(){return time;}};
std::vector<uint8_t> token(const char* plan){
  const char domain[]="rocell.diagnostic-start.v1";
  std::vector<uint8_t> v(domain,domain+sizeof(domain));
  v.resize(v.size()+48,0);
  for(uint64_t t:{uint64_t(1),uint64_t(100)})for(int i=7;i>=0;--i)v.push_back(uint8_t(t>>(i*8)));
  size_t n=strlen(plan);v.push_back(n>>8);v.push_back(n&255);
  v.insert(v.end(),plan,plan+n);v.resize(v.size()+32,0);return v;
}
int main(){
  uint8_t key[32]={1},boot[16]={},nonce[32]={};Crypto crypto;
  for(int scenario=0;scenario<7;++scenario){
    Clock clock;ShoulderBusReservation bus;
    ShoulderAuthorizedStart owner(key,boot,nonce,1,100,"trial",ShoulderSessionScope::PreloadOnly);
    std::string plan=owner.canonical_plan();
    if(scenario==1)plan.replace(plan.find("PRELOAD_ONLY"),12,"PAIR_HOLD");
    auto bytes=token(plan.c_str());int starts=0,checks=0;
    if(scenario==2)bus.reserve();
    if(scenario==4)clock.time=100;
    auto admitted=[&](){++checks;if(scenario==5)clock.time=100;return scenario!=3;};
    auto starter=[&](const char* b,const char* c,ShoulderSessionScope s){
      ++starts;assert(strlen(b)==32&&strcmp(c,"trial")==0&&s==ShoulderSessionScope::PreloadOnly);return scenario!=6;
    };
    bool ok=owner.start(bytes.data(),bytes.size(),clock,crypto,bus,admitted,starter);
    assert(ok==(scenario==0));assert(starts==((scenario==0||scenario==6)?1:0));
    assert(bus.reserved()==(scenario!=1&&scenario!=4));
    assert(!owner.start(bytes.data(),bytes.size(),clock,crypto,bus,admitted,starter));
  }
  std::cout<<"SHOULDER_AUTHORIZED_START_OFFLINE_PASSED\n";
}
