#include <cassert>
#include <fstream>
#include <iterator>
#include <string>
#include "controller_hold_config.h"
int main(int argc,char** argv){
 assert(argc==3);std::ifstream file(argv[1],std::ios::binary);
 std::string bytes((std::istreambuf_iterator<char>(file)),{});
 rocell_diag::ControllerHoldConfigParser parser;
 const bool valid=parser.parse(bytes.data(),bytes.size());assert(valid==(argv[2][0]=='1'));
 assert((parser.get()!=nullptr)==valid);assert(!parser.parse(bytes.data(),bytes.size()));
 if(valid){assert(parser.get()->port==8081);assert(!strcmp(parser.get()->command,"reviewed-hold"));}
}
