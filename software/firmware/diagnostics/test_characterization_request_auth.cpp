#define main admission_fixture_main
#include "test_characterization_admission.cpp"
#undef main
#include "characterization_request_auth.h"
#include "characterization_http_auth.h"
int main(int argc,char** argv){
 assert(argc==3);std::ifstream file(argv[1],std::ios::binary);uint8_t signature[32];file.read(reinterpret_cast<char*>(signature),32);assert(file.gcount()==32);
 Crypto crypto;uint8_t key[32],boot[16];for(int i=0;i<32;++i)key[i]=i;memset(boot,0x11,16);
 rocell_diag::CharacterizationRequestAuth<Crypto> auth(crypto,key,boot);
 const char* path="/rocell/characterization/status";uint8_t empty=0;
 assert(!auth.accept("POST",path,&empty,0,0,signature));
 assert(!auth.accept("GET","/wrong",&empty,0,0,signature));
 assert(!auth.accept("GET",path,&empty,1,0,signature));
 assert(!auth.accept("GET",path,&empty,0,1,signature));
 struct Web{std::string sequence="0",signature;std::string header(const char* name){return std::string(name)=="X-Rocell-Sequence"?sequence:signature;}} web;
 const char* hex="0123456789abcdef";for(auto b:signature){web.signature+=hex[b>>4];web.signature+=hex[b&15];}
 uint32_t accepted=99;web.sequence="00";
 assert(!rocell_diag::authenticate_characterization_http(auth,web,"GET",path,&empty,0,accepted));
 web.sequence="0";assert(rocell_diag::authenticate_characterization_http(auth,web,"GET",path,&empty,0,accepted)&&accepted==0);
 assert(!auth.accept("GET",path,&empty,0,0,signature));
 uint8_t response[32];const uint8_t body[]={'{','}'};
 assert(auth.sign_response(0,200,body,sizeof(body),response));
 std::ofstream output(argv[2],std::ios::binary);output.write(reinterpret_cast<const char*>(response),32);assert(output.good());
 assert(!auth.sign_response(0,200,body,sizeof(body),response));
}
