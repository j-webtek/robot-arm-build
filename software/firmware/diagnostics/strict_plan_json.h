// Bounded lexical preflight for the intentionally narrow session-plan grammar.
// Reject duplicate/out-of-order keys before ArduinoJson can collapse them. Only
// objects, bounded numeric arrays, finite-number syntax and unescaped printable
// ASCII strings are legal. Semantic validation restricts arrays to joint windows.
#pragma once
#include <cstddef>
#include <cstring>
namespace rocell_diag {
class StrictPlanJson {
 public:
  bool check(const char* data,size_t length) {
    data_=data;size_=length;at_=0;nodes_=0;
    return data && length && length<=16384 && object(0) && at_==size_;
  }
 private:
  bool take(char value){if(at_>=size_ || data_[at_]!=value)return false;++at_;return true;}
  bool digit(){return at_<size_ && data_[at_]>='0' && data_[at_]<='9';}
  bool string(size_t& start,size_t& count) {
    if(!take('"'))return false;start=at_;
    while(at_<size_ && data_[at_]!='"') {
      unsigned char c=data_[at_++];if(c<32 || c>126 || c=='\\')return false;
    }
    count=at_-start;return count<=512 && take('"');
  }
  bool number() {
    take('-');
    if(take('0')){if(digit())return false;}
    else {if(!digit())return false;while(digit())++at_;}
    if(take('.')){if(!digit())return false;while(digit())++at_;}
    if(take('e')||take('E')){if(!take('+'))take('-');if(!digit())return false;while(digit())++at_;}
    return true;
  }
  bool object(unsigned depth) {
    if(depth>4 || !take('{'))return false;
    size_t previous=0,previous_length=0;bool first=true;
    if(take('}'))return true;
    do {
      if(++nodes_>80)return false;
      size_t start=0,count=0;if(!string(start,count) || !count || count>64)return false;
      if(!first) {
        size_t common=count<previous_length?count:previous_length;
        int cmp=memcmp(data_+previous,data_+start,common);
        if(cmp>0 || (cmp==0 && previous_length>=count))return false;
      }
      previous=start;previous_length=count;first=false;
      if(!take(':') || at_>=size_)return false;
      if(data_[at_]=='{'){if(!object(depth+1))return false;}
      else if(data_[at_]=='['){if(!array(depth+1))return false;}
      else if(data_[at_]=='"'){size_t s=0,n=0;if(!string(s,n))return false;}
      else if(!number())return false;
      if(take('}'))return true;
    }while(take(','));
    return false;
  }
  bool array(unsigned depth) {
    if(depth>4 || !take('['))return false;
    if(take(']'))return true;
    do {
      if(++nodes_>80 || at_>=size_)return false;
      if(data_[at_]=='['){if(!array(depth+1))return false;}
      else if(!number())return false;
      if(take(']'))return true;
    }while(take(','));
    return false;
  }
  const char* data_=nullptr;size_t size_=0,at_=0,nodes_=0;
};
}
