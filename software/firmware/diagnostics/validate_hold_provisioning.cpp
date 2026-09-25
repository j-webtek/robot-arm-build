// Offline host executable: use the installed candidate's headers via -I.
// No board/serial/network adapters or firmware deployment code are linked.
#include <cstdio>
#include <controller_hold_config.h>
#ifdef _WIN32
#include <io.h>
#include <fcntl.h>
#endif
int main(){
#ifdef _WIN32
  if(_setmode(_fileno(stdin),_O_BINARY)==-1||_setmode(_fileno(stdout),_O_BINARY)==-1)return 3;
#endif
  char input[2048];const size_t count=fread(input,1,sizeof(input),stdin);
  if(ferror(stdin)||count==0||count==sizeof(input))return 2;
  rocell_diag::ControllerHoldConfigParser parser;
  if(!parser.parse(input,count))return 2;
  fputs("POLICY_ACCEPTED\n",stdout);return 0;
}
