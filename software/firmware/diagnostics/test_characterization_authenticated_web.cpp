#define main admission_fixture_main
#include "test_characterization_admission.cpp"
#undef main
#include <map>
#include <functional>
enum HTTPMethod { HTTP_GET=0,HTTP_POST=1 };
#include "characterization_authenticated_web.h"
struct Web {
 std::map<std::string,std::function<void()>> routes;
 std::map<std::string,std::string> headers,out;
 int status=0,sends=0;unsigned collected=0;std::string response;
 void collectHeaders(const char**,size_t n){collected=n;}
 void on(const char* path,HTTPMethod,std::function<void()> handler){routes[path]=handler;}
 std::string arg(const char*){return "";}
 std::string header(const char* name){return headers[name];}
 void sendHeader(const char* name,const char* value){out[name]=value;}
 void send(int code,const char*,const char* raw){status=code;response=raw;++sends;}
};
int main(int argc,char** argv){
 assert(argc==3);std::ifstream input(argv[1],std::ios::binary);uint8_t signature[32];input.read(reinterpret_cast<char*>(signature),32);assert(input.gcount()==32);
 Crypto crypto;uint8_t key[32],boot[16];for(int i=0;i<32;++i)key[i]=i;memset(boot,0x11,16);
 rocell_diag::CharacterizationRequestAuth<Crypto> gate(crypto,key,boot);Web web;
 rocell_diag::CharacterizationAuthenticatedWeb<decltype(gate),Web> wrapped(gate,web);
 wrapped.collect_headers();assert(web.collected==2);unsigned calls=0;
 wrapped.on("/rocell/characterization/status",HTTP_GET,[&](){++calls;assert(wrapped.authenticated());wrapped.send(200,"application/json","{}");wrapped.send(200,"text/plain","ignored");});
 auto handler=web.routes.at("/rocell/characterization/status");handler();assert(web.status==403&&!calls);
 web.headers["X-Rocell-Sequence"]="0";const char* hex="0123456789abcdef";
 for(auto b:signature){web.headers["X-Rocell-Signature"]+=hex[b>>4];web.headers["X-Rocell-Signature"]+=hex[b&15];}
 handler();assert(calls==1&&web.status==200&&web.response=="{}"&&web.sends==2);
 std::ofstream output(argv[2]);output<<web.out["X-Rocell-Signature"];assert(output.good());
 handler();assert(calls==1&&web.status==403&&!wrapped.authenticated());
}
