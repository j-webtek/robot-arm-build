#pragma once
#include <cstddef>
#include <cstring>
namespace rocell_diag {
inline int payload_base64_digit(char c) {
  if(c>='A'&&c<='Z')return c-'A';if(c>='a'&&c<='z')return c-'a'+26;
  if(c>='0'&&c<='9')return c-'0'+52;if(c=='+')return 62;if(c=='/')return 63;return -1;
}
// Strict standard base64, including zero padding bits; no whitespace/URL alphabet.
inline bool decode_payload_base64(const char* text,char (&out)[257],size_t& written) {
  written=0;out[0]=0;if(!text)return false;const size_t size=strlen(text);
  if(!size || size>344 || size%4)return false;
  for(size_t i=0;i<size;i+=4) {
    const int a=payload_base64_digit(text[i]),b=payload_base64_digit(text[i+1]);
    const bool pad2=text[i+2]=='=',pad3=text[i+3]=='=';
    const int c=pad2?0:payload_base64_digit(text[i+2]),d=pad3?0:payload_base64_digit(text[i+3]);
    if(a<0||b<0||c<0||d<0||(pad2&&!pad3)||((pad2||pad3)&&i+4!=size)||
       (pad2&&(b&15))||(!pad2&&pad3&&(c&3)))return false;
    const size_t count=pad2?1:pad3?2:3;
    if(written+count>256)return false;
    out[written++]=static_cast<char>((a<<2)|(b>>4));
    if(count>1)out[written++]=static_cast<char>((b<<4)|(c>>2));
    if(count>2)out[written++]=static_cast<char>((c<<6)|d);
  }
  out[written]=0;return true;
}
}
