#include "reviewed_hover_live_admission.h"
#include <cassert>
#include <string>

using namespace rocell_diag;
int main(){
  uint8_t boot[16],release[32];
  for(auto& b:boot)b=0xab;
  for(auto& b:release)b=0xcd;
  std::string body="RCHL2:"+std::string(32,'a');
  for(unsigned i=0;i<16;++i)body[6+2*i+1]='b';
  body+=":01:01:"+std::string(64,'e')+":"+std::string(64,'c')+
        ":LIVE_NONCONTACT";
  const size_t release_at=108+2;
  for(unsigned i=0;i<32;++i)body[release_at+2*i+1]='d';
  auto recipe_ok=[](const uint8_t* ids,size_t count,const uint8_t* digest){
    if(count!=1||ids[0]!=ReviewedHoverManifest::A_HOVER)return false;
    for(unsigned i=0;i<32;++i)if(digest[i]!=0xee)return false;
    return true;
  };
  ReviewedHoverLiveAdmission out;
  auto parse=[&](const std::string& input){
    return ReviewedHoverLiveAdmission::parse(input.data(),input.size(),
                                             boot,release,recipe_ok,out);};
  assert(parse(body)&&out.count==1&&out.pose_ids[0]==1&&out.boot[0]==0xab&&
         out.release_digest[0]==0xcd);
  std::string changed=body;changed[0]='M';assert(!parse(changed));
  changed=body;changed[6]='0';assert(!parse(changed));
  changed=body;changed[release_at]='0';assert(!parse(changed));
  changed=body;changed[43+2]='0';assert(!parse(changed));
  changed=body;changed[42]='0';changed[43]='5';assert(!parse(changed));
  changed=body;changed.replace(changed.size()-15,15,"LIVE_CONTACT");assert(!parse(changed));
  changed=body.substr(0,body.size()-1);assert(!parse(changed));
  changed=body;changed[43+2]='f';assert(!parse(changed));
  auto recipe_bad=[](const uint8_t*,size_t,const uint8_t*){return false;};
  assert(!ReviewedHoverLiveAdmission::parse(body.data(),body.size(),boot,release,
                                             recipe_bad,out));
  assert(out.count==1&&out.pose_ids[0]==1); // Failure never commits new output.
  return 0;
}
