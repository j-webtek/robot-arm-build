#include <cassert>
#include <fstream>
#include <iterator>
#include <string>
#include "startup_plan_structure.h"
int main(int argc,char** argv){
 assert(argc==4);std::ifstream file(argv[1],std::ios::binary);
 std::string bytes((std::istreambuf_iterator<char>(file)),{});
 using namespace rocell_diag;
 StartupPositionPolicy p={};for(auto& w:p.joints)w={1024,3071};p.drift_tolerance=2;
 p.minimum_separation_us=100000;p.maximum_wait_us=1000000;p.maximum_pair_us=1000;
 p.maximum_scan_us=100000;p.maximum_age_us=100000;
 WholeArmBaselinePolicy normal={};for(auto& w:normal.joints)w={1024,3071};
 normal.tracking_tolerance=2;normal.maximum_pair_us=1000;normal.maximum_scan_us=100000;normal.maximum_age_us=100000;
 StartupPlanStructure parser;BoundStartRequest request;
 assert(!parser.copy_bound_request(request));
 const bool valid=parser.parse(bytes.data(),bytes.size(),"0123456789abcdef0123456789abcdef",argv[3],"test-only",p,0,normal);
 assert(valid==(std::string(argv[2])=="yes"));
 assert(!parser.copy_bound_request(request)); // Structure alone does not bind command bytes.
}
