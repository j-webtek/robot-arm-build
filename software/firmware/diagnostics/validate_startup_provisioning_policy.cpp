// Host-only validator. Angle include selects the hash-checked candidate headers,
// not adjacent current-source headers that may have changed since compilation.
#include <iostream>
#include <string>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
#include <controller_startup_config.h>
int main(){
#ifdef _WIN32
 if(_setmode(_fileno(stdin),_O_BINARY)==-1||_setmode(_fileno(stdout),_O_BINARY)==-1)return 3;
#endif
 std::string policy;char value;
 while(std::cin.get(value)){if(policy.size()>=4096)return 2;policy.push_back(value);}
 if(!std::cin.eof())return 3;
 rocell_diag::ControllerStartupConfigParser parser;
 if(!parser.parse(policy.data(),policy.size(),"roarm-m3-example20260115-elbow-v1")||!parser.get())return 2;
 std::cout<<"POLICY_ACCEPTED\n";return 0;
}
