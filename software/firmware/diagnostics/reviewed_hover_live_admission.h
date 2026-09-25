// Structural parser for future live admission. No route or hardware access.
#pragma once
#include "reviewed_hover_manifest.h"
#include <cstddef>
#include <cstdint>
#include <cstring>

namespace rocell_diag {
struct ReviewedHoverLiveAdmission {
  uint8_t boot[16]{},recipe_digest[32]{},release_digest[32]{};
  uint8_t pose_ids[ReviewedHoverManifest::max_legs]{};
  uint8_t count=0;
  static int nibble(char c){
    return c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
  }
  static bool hex(const char* text,size_t bytes,uint8_t* output){
    for(size_t i=0;i<bytes;++i){
      const int hi=nibble(text[2*i]),lo=nibble(text[2*i+1]);
      if(hi<0||lo<0)return false;
      output[i]=uint8_t((hi<<4)|lo);
    }
    return true;
  }
  static bool nonzero(const uint8_t* bytes,size_t size){
    uint8_t aggregate=0;for(size_t i=0;i<size;++i)aggregate|=bytes[i];
    return aggregate!=0;
  }
  static bool equal(const uint8_t* left,const uint8_t* right,size_t size){
    uint8_t difference=0;
    for(size_t i=0;i<size;++i)difference|=left[i]^right[i];
    return difference==0;
  }
  template<class RecipeMatches>
  static bool parse(const char* body,size_t length,const uint8_t (&expected_boot)[16],
                    const uint8_t (&expected_release)[32],RecipeMatches& recipe_matches,
                    ReviewedHoverLiveAdmission& output){
    if(!body||length<190||std::memcmp(body,"RCHL2:",6)||body[38]!=':'||
       body[41]!=':')return false;
    uint8_t boot[16]{},count_byte[1]{},recipe[32]{},release[32]{};
    if(!hex(body+6,16,boot)||!hex(body+39,1,count_byte))return false;
    const size_t count=count_byte[0];
    if(!count||count>ReviewedHoverManifest::max_legs||length!=188+2*count)
      return false;
    const size_t recipe_at=43+2*count,release_at=108+2*count;
    if(body[42+2*count]!=':'||body[107+2*count]!=':'||
       body[172+2*count]!=':'||
       std::memcmp(body+173+2*count,"LIVE_NONCONTACT",15))return false;
    uint8_t ids[ReviewedHoverManifest::max_legs]{};
    if(!hex(body+42,count,ids)||!hex(body+recipe_at,32,recipe)||
       !hex(body+release_at,32,release)||
       !nonzero(boot,16)||!nonzero(release,32)||
       !equal(boot,expected_boot,16)||!equal(release,expected_release,32)||
       !ReviewedHoverManifest::validate(ids,count)||
       !recipe_matches(ids,count,recipe))return false;
    ReviewedHoverLiveAdmission parsed;
    std::memcpy(parsed.boot,boot,16);std::memcpy(parsed.recipe_digest,recipe,32);
    std::memcpy(parsed.release_digest,release,32);
    std::memcpy(parsed.pose_ids,ids,count);parsed.count=uint8_t(count);
    output=parsed;return true;
  }
};
}
