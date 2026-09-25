// Independent read-only recovery authentication. Same-task snapshot only.
// Replayed requests may read again but cannot mutate campaign/command sequence.
// Host-generated fresh nonces bind replies; host must enforce a request deadline.
#pragma once
#include <cstring>
namespace rocell_diag {
template<class Crypto,class Controller,class Web> class CharacterizationRecoveryRoute {
 public:
  CharacterizationRecoveryRoute(Crypto& crypto,Controller& controller,Web& web,
      const uint8_t (&key)[32],const uint8_t (&boot)[16])
      :crypto_(crypto),controller_(controller),web_(web){memcpy(key_,key,32);memcpy(boot_,boot,16);}
  ~CharacterizationRecoveryRoute(){volatile uint8_t* p=key_;for(unsigned i=0;i<32;++i)p[i]=0;}
  CharacterizationRecoveryRoute(const CharacterizationRecoveryRoute&)=delete;
  CharacterizationRecoveryRoute& operator=(const CharacterizationRecoveryRoute&)=delete;
  void register_route(){
    if(registered_)return;registered_=true;
    web_.on("/rocell/characterization/recovery-read",HTTP_POST,[this](){handle();});
  }
 private:
  void handle(){
    web_.sendHeader("Cache-Control","no-store");
    auto body=web_.arg("plain");
    if(web_.args()!=1||web_.argName(0)!="plain"||body.length()!=128){web_.send(400,"text/plain","");return;}
    uint8_t raw[64]={};
    for(unsigned i=0;i<128;++i){char c=body[i];int v=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
      if(v<0){web_.send(400,"text/plain","");return;}raw[i/2]|=uint8_t(v<<(i%2?0:4));}
    uint8_t message[112]={},signature[32];size_t n=0;
    const char request_domain[]="RCCRECOVERYREQUEST01";
    memcpy(message,request_domain,sizeof(request_domain));n=sizeof(request_domain);
    memcpy(message+n,boot_,16);n+=16;memcpy(message+n,raw,32);n+=32;
    uint8_t any=0;for(auto byte:key_)any|=byte;
    if(!any||!crypto_.hmac_sha256(key_,message,n,signature)){web_.send(403,"text/plain","");return;}
    uint8_t difference=0;for(unsigned i=0;i<32;++i)difference|=signature[i]^raw[32+i];
    if(difference){web_.send(403,"text/plain","");return;}
    char snapshot[640]={};size_t size=controller_.recovery_snapshot(snapshot,sizeof(snapshot));
    unsigned status=size?200:409;
    uint8_t digest[32];if(!crypto_.sha256(reinterpret_cast<const uint8_t*>(snapshot),size,digest)){web_.send(500,"text/plain","");return;}
    const char response_domain[]="RCCRECOVERYRESPONSE01";
    memcpy(message,response_domain,sizeof(response_domain));n=sizeof(response_domain);
    memcpy(message+n,boot_,16);n+=16;memcpy(message+n,raw,32);n+=32;
    message[n++]=uint8_t(status>>8);message[n++]=uint8_t(status);
    memcpy(message+n,digest,32);n+=32;
    if(!crypto_.hmac_sha256(key_,message,n,signature)){web_.send(500,"text/plain","");return;}
    char hex[65]={};const char* digits="0123456789abcdef";
    for(unsigned i=0;i<32;++i){hex[2*i]=digits[signature[i]>>4];hex[2*i+1]=digits[signature[i]&15];}
    web_.sendHeader("X-Rocell-Signature",hex);web_.send(status,"application/json",snapshot);
  }
  Crypto& crypto_;Controller& controller_;Web& web_;uint8_t key_[32],boot_[16];bool registered_=false;
};
}
