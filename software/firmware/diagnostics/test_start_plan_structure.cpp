#include <fstream>
#include <string>
#include <iterator>
#include <cassert>
#include "start_plan_structure.h"
int main(int argc,char** argv){
  assert(argc==3);std::ifstream stream(argv[1],std::ios::binary);
  std::string bytes((std::istreambuf_iterator<char>(stream)),{});
  rocell_diag::StartPlanStructure parser;
  const bool ok=parser.parse(bytes.data(),bytes.size(),"11111111111111111111111111111111","test-reference");
  assert(ok==(strcmp(argv[2],"yes")==0));
  assert(!parser.parse("{}",2,"11111111111111111111111111111111","test-reference"));
}
