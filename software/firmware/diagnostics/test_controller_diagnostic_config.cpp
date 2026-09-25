#include <cassert>
#include <fstream>
#include <iterator>
#include <string>
#include "controller_diagnostic_config.h"
struct File {
  int mode,closed=0;explicit operator bool() const{return mode!=1;}
  size_t size() const{return mode==2?31:mode==3?33:32;}
  int read(uint8_t* bytes,size_t count){
    assert(count==32);for(size_t i=0;i<32;++i)bytes[i]=mode==5?0:mode==6?static_cast<uint8_t>(i):static_cast<uint8_t>(31-i);
    return mode==4?31:32;
  }
  void close(){++closed;}
};
int main(int argc,char** argv){
  assert(argc==3);std::ifstream file(argv[1],std::ios::binary);
  std::string bytes((std::istreambuf_iterator<char>(file)),{});
  rocell_diag::ControllerDiagnosticConfigParser parser;
  const bool valid=parser.parse(bytes.data(),bytes.size(),"test-reference");
  assert(valid==(std::string(argv[2])=="yes"));assert((parser.get()!=nullptr)==valid);
  if(valid){assert(parser.get()->port==8081 && parser.get()->maximum_speed==40);
    assert(parser.get()->whole.joints[0].minimum==1900);}
  assert(!parser.parse("{}",2,"test-reference") && !parser.get());
  rocell_diag::DiagnosticKeyMaterial key;uint8_t out[32];
  for(int mode=0;mode<=6;++mode){File source{mode,0};
    assert(key.load(source)==(mode==0));assert(source.closed==1);
    assert(key.copy_to(out)==(mode==0));
    for(size_t i=0;i<32;++i)assert(out[i]==(mode==0?31-i:0));
  }
}
