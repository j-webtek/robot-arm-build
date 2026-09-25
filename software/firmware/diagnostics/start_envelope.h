// Authentication/framing only. Returned bytes STILL require strict plan parsing,
// origin/identity validation and fresh physical admission before any dispatch.
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
namespace rocell_diag {
struct AuthenticatedPlanView {const uint8_t* bytes=nullptr;size_t length=0;};
class StartEnvelopeGate {
 public:
  StartEnvelopeGate(const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires)
      :issued_(issued),expires_(expires),used_(false),valid_(false) {
    memcpy(key_,key,32);memcpy(boot_,boot,16);memcpy(nonce_,nonce,32);
    uint8_t nonzero=0;for(uint8_t byte:key_)nonzero|=byte;
    valid_=nonzero && issued<=INT64_MAX && expires<=INT64_MAX &&
        expires>issued && expires-issued<=30000000;
  }
  ~StartEnvelopeGate(){volatile uint8_t* p=key_;for(size_t i=0;i<32;++i)p[i]=0;}
  StartEnvelopeGate(const StartEnvelopeGate&)=delete;
  StartEnvelopeGate& operator=(const StartEnvelopeGate&)=delete;
  template<class Crypto>
  bool consume(const uint8_t* token,size_t length,uint64_t now,Crypto& crypto,
               AuthenticatedPlanView& view) {
    view={};
    if(used_)return false;
    used_=true; // Never refund a failed, expired or subsequently rejected attempt.
    static const char domain[]="rocell.diagnostic-start.v1";
    const size_t prefix=sizeof(domain)+64;
    if(!valid_ || now<issued_ || now>=expires_ || !token ||
        length<prefix+2+1+32 || length>prefix+2+16384+32)return false;
    uint8_t digest[32]={};
    if(!crypto.hmac_sha256(key_,token,length-32,digest))return false;
    uint8_t difference=0;
    for(size_t i=0;i<32;++i)difference|=digest[i]^token[length-32+i];
    if(difference || memcmp(token,domain,sizeof(domain)) ||
       memcmp(token+sizeof(domain),boot_,16) || memcmp(token+sizeof(domain)+16,nonce_,32))return false;
    const uint8_t* times=token+sizeof(domain)+48;
    if(read64(times)!=issued_ || read64(times+8)!=expires_)return false;
    const size_t count=(static_cast<size_t>(token[prefix])<<8)|token[prefix+1];
    if(count!=length-prefix-2-32)return false;
    // Borrowed view: caller must retain immutable request storage through parsing.
    view.bytes=token+prefix+2;view.length=count;return true;
  }
 private:
  static uint64_t read64(const uint8_t* bytes){uint64_t value=0;for(int i=0;i<8;++i)value=(value<<8)|bytes[i];return value;}
  uint8_t key_[32],boot_[16],nonce_[32];uint64_t issued_,expires_;
  bool used_,valid_;
};
}
