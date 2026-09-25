// Verify the installed r20 recovery whitelist, not merely the JSON parser.
#include <cassert>
#include <fstream>
#include <iterator>
#include <string>
#include <controller_hold_config.h>
#include <supported_recovery_board_policy.h>
int main(int argc,char** argv){
  assert(argc==3);
  for(int i=1;i<=2;++i){
    std::ifstream input(argv[i],std::ios::binary);
    std::string raw((std::istreambuf_iterator<char>(input)),{});
    rocell_diag::ControllerHoldConfigParser parser;
    assert(parser.parse(raw.data(),raw.size()));
    const auto& config=*parser.get();
    const bool admitted=config.port==8081&&
        !strcmp(config.command,"r7-supported-hold-20260918")&&
        rocell_diag::reviewed_recovery_source(config.policy);
    assert(admitted==(i==1));
  }
}
