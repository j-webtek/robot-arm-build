// Header decoder for registered WebServer handlers. Actual method/path/body are
// supplied by the adapter, not trusted header values. No network registration.
#pragma once
#include "characterization_request_auth.h"
namespace rocell_diag {
template<class Gate,class Web> bool authenticate_characterization_http(
    Gate& gate,Web& web,const char* method,const char* path,const uint8_t* body,size_t size,uint32_t& accepted_sequence){
  const auto sequence=web.header("X-Rocell-Sequence"),signature=web.header("X-Rocell-Signature");
  if(!sequence.length()||sequence.length()>4||signature.length()!=64)return false;
  if(sequence.length()>1&&sequence[0]=='0')return false;
  uint32_t value=0;for(unsigned i=0;i<sequence.length();++i){
    if(sequence[i]<'0'||sequence[i]>'9')return false;value=value*10+sequence[i]-'0';}
  if(value>=4096)return false;
  uint8_t bytes[32]={};
  for(unsigned i=0;i<64;++i){char c=signature[i];int digit=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
    if(digit<0)return false;if(i%2)bytes[i/2]|=digit;else bytes[i/2]=digit<<4;}
  if(!gate.accept(method,path,body,size,value,bytes))return false;
  accepted_sequence=value;return true;
}
}
