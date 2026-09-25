// Per-request HMAC binding for the future same-task WebServer adapter. The board
// supplies actual method/path/body; never accept these values from auth headers.
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
namespace rocell_diag {
template<class Crypto> class CharacterizationRequestAuth {
 public:
  CharacterizationRequestAuth(Crypto& crypto,const uint8_t (&key)[32],const uint8_t (&boot)[16])
      :crypto_(crypto){memcpy(key_,key,32);memcpy(boot_,boot,16);for(auto b:key)valid_|=b!=0;}
  ~CharacterizationRequestAuth(){volatile uint8_t* p=key_;for(unsigned i=0;i<32;++i)p[i]=0;}
  CharacterizationRequestAuth(const CharacterizationRequestAuth&)=delete;
  CharacterizationRequestAuth& operator=(const CharacterizationRequestAuth&)=delete;
  bool accept(const char* method,const char* path,const uint8_t* body,size_t size,
              uint32_t sequence,const uint8_t (&signature)[32]){
    if(!valid_||response_pending_||sequence!=next_||next_>=4096||!method||!path||(!body&&size)||size>1024)return false;
    if(strcmp(method,"GET")&&strcmp(method,"POST"))return false;
    size_t path_size=strlen(path);if(!path_size||path_size>128)return false;
    uint8_t body_hash[32],expected[32];if(!crypto_.sha256(body,size,body_hash))return false;
    size_t n=0;const char domain[]="RCCREQUEST01";
    for(char c:domain)buffer_[n++]=uint8_t(c);
    memcpy(buffer_+n,boot_,16);n+=16;
    for(int shift=24;shift>=0;shift-=8)buffer_[n++]=uint8_t(sequence>>shift);
    buffer_[n++]=!strcmp(method,"GET")?0:1;buffer_[n++]=uint8_t(path_size);
    memcpy(buffer_+n,path,path_size);n+=path_size;memcpy(buffer_+n,body_hash,32);n+=32;
    if(!crypto_.hmac_sha256(key_,buffer_,n,expected))return false;
    uint8_t difference=0;for(unsigned i=0;i<32;++i)difference|=expected[i]^signature[i];
    if(difference)return false;
    ++next_;response_pending_=true;return true; // Consume before handler; lost replies never refund.
  }
  bool sign_response(uint32_t sequence,unsigned status,const uint8_t* body,size_t size,uint8_t (&signature)[32]){
    if(!response_pending_||!next_||sequence!=next_-1||status<100||status>599||(!body&&size)||size>4095)return false;
    response_pending_=false;
    uint8_t digest[32];if(!crypto_.sha256(body,size,digest))return false;
    size_t n=0;const char domain[]="RCCRESPONSE01";
    for(char c:domain)buffer_[n++]=uint8_t(c);
    memcpy(buffer_+n,boot_,16);n+=16;
    for(int shift=24;shift>=0;shift-=8)buffer_[n++]=uint8_t(sequence>>shift);
    buffer_[n++]=uint8_t(status>>8);buffer_[n++]=uint8_t(status);
    memcpy(buffer_+n,digest,32);n+=32;
    return crypto_.hmac_sha256(key_,buffer_,n,signature);
  }
 private:
  Crypto& crypto_;uint8_t key_[32],boot_[16],buffer_[224]={};uint32_t next_=0;bool valid_=false,response_pending_=false;
};
}
