#define ROCELL_BOARD_FIXTURE_ONLY
#include "test_characterization_board_services.cpp"
#include <map>
#include <functional>
#include <string>
constexpr int HTTP_GET=0,HTTP_POST=1;
#include "characterization_composition.h"
#include "characterization_evidence.h"
struct Web {
 std::map<std::string,std::function<void()>> routes;std::map<std::string,std::string> headers,out;
 std::string body,response;int status=0;
 void collectHeaders(const char**,size_t){}
 void on(const char* path,int,std::function<void()> f){routes[path]=f;}
 auto header(const char* name){return headers[name];}
 auto arg(const char*){return body;}std::string argName(int){return "plain";}
 int args(){return body.empty()?0:1;}
 void sendHeader(const char* k,const char* v){out[k]=v;}
 void send(int s,const char*,const char* text){status=s;response=text;}
};
int main(int argc,char** argv){
 if(argc>3){
   const std::string hypothesis=argv[3];
   assert(hypothesis=="constant10"||hypothesis=="directional"||hypothesis=="frozen_reverse"||hypothesis=="transient_reverse"||hypothesis=="delayed_reverse"||hypothesis=="frozen_all"||hypothesis=="bad_lower"||hypothesis=="ghost_small"||hypothesis=="ghost_delayed_reverse");
   st.forward0=st.reverse0=10;st.p[1]=st.g[1]+10;
   if(hypothesis=="directional"){st.reverse0=6;st.reverse1=-4;}
   st.fail_reverse=hypothesis=="frozen_reverse"||hypothesis=="transient_reverse"||hypothesis=="delayed_reverse";
   st.reverse_model=hypothesis=="transient_reverse"?1:hypothesis=="delayed_reverse"?2:0;
   if(hypothesis=="frozen_all"){st.fail_all=true;st.p[1]=st.g[1];st.p[2]=st.g[2];}
 }
 Crypto crypto;auto evidence=std::make_unique<rocell_diag::CharacterizationEvidence>();
 // Fixed pilot baseline for these test-only selectors; no hardware involved.
 if(argc>1&&(std::string(argv[1])=="ab_control"||std::string(argv[1])=="ab_candidate")){
   st.g[1]=2389;st.g[2]=1725;st.p[1]=2391;st.p[2]=1724;
   st.forward0=9;st.forward1=-7;
   st.band_model=argc<=3||std::string(argv[3])!="directional";
   if(argc<=3||std::string(argv[3])!="directional"){st.reverse0=2;st.reverse1=-1;}
 }
 if(argc>1&&std::string(argv[1])=="forward_repeat"){
   st.g[1]=2378;st.g[2]=1736;st.p[1]=2387;st.p[2]=1730;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="reverse_candidate"){
   st.g[1]=2378;st.g[2]=1736;st.p[1]=2387;st.p[2]=1730;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="reverse_control"){
   st.g[1]=2385;st.g[2]=1729;st.p[1]=2387;st.p[2]=1728;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="heldout_candidate"){
   st.g[1]=2386;st.g[2]=1728;st.p[1]=2388;st.p[2]=1727;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="heldout_control"){
   st.g[1]=2388;st.g[2]=1726;st.p[1]=2390;st.p[2]=1725;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="second_heldout_candidate"){
   st.g[1]=2389;st.g[2]=1725;st.p[1]=2390;st.p[2]=1724;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="second_heldout_control"){
   st.g[1]=2378;st.g[2]=1736;st.p[1]=2388;st.p[2]=1729;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="mapping_batch"){
   st.g[1]=2386;st.g[2]=1728;st.p[1]=2391;st.p[2]=1724;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="separated_mapping_batch"){
   st.g[1]=2381;st.g[2]=1733;st.p[1]=2387;st.p[2]=1728;st.validation_model=true;
 }
 if(argc>1&&std::string(argv[1])=="fine_lookup_validation"){
   st.g[1]=2387;st.g[2]=1727;st.p[1]=2389;st.p[2]=1726;st.validation_model=true;
 }
 if(argc>1&&(std::string(argv[1])=="local_interval_campaign"||
             std::string(argv[1])=="ghost_pair_transition_campaign")){
   st.g[1]=2389;st.g[2]=1725;st.p[1]=2391;st.p[2]=1724;st.validation_model=true;
 }
 if(argc>3&&std::string(argv[3])=="ghost_small")st.ghost_small_model=true;
 if(argc>3&&std::string(argv[3])=="ghost_delayed_reverse")st.ghost_delayed_reverse_model=true;
 if(argc>3&&std::string(argv[3])=="bad_lower")st.bad_lower=true;
 RocellCharacterizationServices<rocell_diag::CharacterizationEvidence> services{*evidence};Web web;
 uint8_t key[32],boot[16];for(int i=0;i<32;++i)key[i]=i;memset(boot,0x11,16);
 uint16_t bounds[7][2];for(auto& b:bounds){b[0]=0;b[1]=4095;}
 using Composition=rocell_diag::CharacterizationComposition<Crypto,decltype(services),Clock,Web>;
 const bool matched=argc>1&&std::string(argv[1])=="matched";
 auto app=std::make_unique<Composition>(crypto,services,rocellConfiguredClock,web,key,boot,bounds,
   argc>1&&std::string(argv[1])=="smoke"?rocell_diag::CharacterizationPattern::Smoke:
   argc>1&&std::string(argv[1])=="matrix"?rocell_diag::CharacterizationPattern::Matrix:
   argc>1&&std::string(argv[1])=="repeatability"?rocell_diag::CharacterizationPattern::Repeatability:
   argc>1&&std::string(argv[1])=="ab_control"?rocell_diag::CharacterizationPattern::ABControl:
   argc>1&&std::string(argv[1])=="ab_candidate"?rocell_diag::CharacterizationPattern::ABCandidate:
   argc>1&&std::string(argv[1])=="forward_repeat"?rocell_diag::CharacterizationPattern::ForwardRepeat:
   argc>1&&std::string(argv[1])=="reverse_candidate"?rocell_diag::CharacterizationPattern::ReverseCandidate:
   argc>1&&std::string(argv[1])=="reverse_control"?rocell_diag::CharacterizationPattern::ReverseControl:
   argc>1&&std::string(argv[1])=="heldout_candidate"?rocell_diag::CharacterizationPattern::HeldoutCandidate:
   argc>1&&std::string(argv[1])=="heldout_control"?rocell_diag::CharacterizationPattern::HeldoutControl:
   argc>1&&std::string(argv[1])=="second_heldout_candidate"?rocell_diag::CharacterizationPattern::SecondHeldoutCandidate:
   argc>1&&std::string(argv[1])=="second_heldout_control"?rocell_diag::CharacterizationPattern::SecondHeldoutControl:
   argc>1&&std::string(argv[1])=="mapping_batch"?rocell_diag::CharacterizationPattern::MappingBatch:
   argc>1&&std::string(argv[1])=="separated_mapping_batch"?rocell_diag::CharacterizationPattern::SeparatedMappingBatch:
   argc>1&&std::string(argv[1])=="fine_lookup_validation"?rocell_diag::CharacterizationPattern::FineLookupValidation:
   argc>1&&std::string(argv[1])=="local_interval_campaign"?rocell_diag::CharacterizationPattern::LocalIntervalCampaign:
   argc>1&&std::string(argv[1])=="ghost_pair_transition_campaign"?rocell_diag::CharacterizationPattern::GhostPairTransitionCampaign:
   matched?rocell_diag::CharacterizationPattern::Matched:rocell_diag::CharacterizationPattern::Legacy);
 app->register_routes();assert(web.routes.size()==10&&!st.reads&&!st.writes);
 // Test-only RPC relay: real host signatures enter unchanged via localhost.
 // TICK models autonomous firmware polling even if a reply is lost.
 if(argc>2&&std::string(argv[2])=="rpc"){
   std::string operation;
   while(std::cin>>operation){
     if(operation=="SNAPSHOT"){
       auto reads=st.reads,writes=st.writes;char snapshot[640]={};
       assert(app->recovery_snapshot(snapshot,sizeof(snapshot)));
       assert(st.reads==reads&&st.writes==writes);
       std::cout<<snapshot<<std::endl;continue;
     }
     if(operation=="TICK"){
       unsigned count;std::cin>>count;assert(count<=100);
       for(unsigned i=0;i<count;++i){rocellConfiguredClock.tick+=100000;app->poll();}
       std::cout<<st.writes<<std::endl;continue;
     }
     assert(operation=="CALL");
     std::string path,sequence,signature,body;
     std::cin>>path>>sequence>>signature>>body;
     web.body=body=="-"?"":body;web.out.clear();
     web.headers["X-Rocell-Sequence"]=sequence;
     web.headers["X-Rocell-Signature"]=signature;
     auto before_reads=st.reads,before_writes=st.writes;
     assert(web.routes.count(path));web.routes[path]();
     if(path=="/rocell/characterization/recovery-read"||path=="/rocell/characterization/reference")assert(st.reads==before_reads&&st.writes==before_writes);
     const auto seq=web.out["X-Rocell-Sequence"],sig=web.out["X-Rocell-Signature"];
     std::cout<<web.status<<" "<<(seq.empty()?"-":seq)<<" "<<(sig.empty()?"-":sig)<<" ";
     if(web.response.empty())std::cout<<"-";
     else for(unsigned char c:web.response){const char* hex="0123456789abcdef";std::cout<<hex[c>>4]<<hex[c&15];}
     std::cout<<std::endl;
   }
   return 0;
 }
 auto sign=[&](const char* path,bool post,unsigned sequence){
   std::vector<uint8_t> raw;const char domain[]="RCCREQUEST01";
   raw.insert(raw.end(),domain,domain+sizeof(domain));raw.insert(raw.end(),boot,boot+16);
   for(int n=24;n>=0;n-=8)raw.push_back(uint8_t(sequence>>n));
   raw.push_back(post?1:0);raw.push_back(uint8_t(strlen(path)));raw.insert(raw.end(),path,path+strlen(path));
   uint8_t hash[32],signature[32];assert(crypto.sha256(reinterpret_cast<const uint8_t*>(web.body.data()),web.body.size(),hash));raw.insert(raw.end(),hash,hash+32);
   assert(crypto.hmac_sha256(key,raw.data(),raw.size(),signature));
   char seq[12];snprintf(seq,sizeof(seq),"%u",sequence);
   web.headers["X-Rocell-Sequence"]=seq;web.headers["X-Rocell-Signature"]="";
   const char* hex="0123456789abcdef";for(auto b:signature){web.headers["X-Rocell-Signature"]+=hex[b>>4];web.headers["X-Rocell-Signature"]+=hex[b&15];}
 };
 const char* prepare="/rocell/characterization/prepare";
 web.routes[prepare]();assert(web.status==403&&!rocellDiagnosticOwned);
 sign(prepare,true,0);web.routes[prepare]();assert(web.status==202&&rocellDiagnosticOwned&&!st.reads&&!st.writes);
 for(int i=0;i<4;++i){rocellConfiguredClock.tick+=200000;app->poll();}
 assert(st.reads==84&&!st.writes);
 const char* challenge="/rocell/characterization/challenge";
 sign(challenge,false,1);web.routes[challenge]();assert(web.status==200&&web.response.size()==
   (argc>1&&std::string(argv[1])=="smoke"?360u:
    argc>1&&std::string(argv[1])=="local_interval_campaign"?440u:448u));
 assert(web.out["X-Rocell-Signature"].size()==64);
 if(argc>1)std::cout<<web.response<<"\n"<<web.out["X-Rocell-Signature"]<<std::endl;
 web.routes[challenge]();assert(web.status==403);
 const char* status="/rocell/characterization/status";
 sign(status,false,2);web.routes[status]();assert(web.status==200&&web.response.find("AWAITING_AUTHORIZATION")!=std::string::npos);
 assert(!st.writes&&evidence->size()==0);
 if(argc>1){
   std::getline(std::cin,web.body);assert(!web.body.empty());
   const char* start="/rocell/characterization/start";
   sign(start,true,3);web.routes[start]();
   assert(web.status==200&&!st.writes);
   web.body.clear();sign(status,false,4);web.routes[status]();
   assert(web.status==200&&web.response.find("BASELINE")!=std::string::npos);
   bool waiting=false;
   unsigned sequence=5;
   for(unsigned n=0;n<40;++n){
     rocellConfiguredClock.tick+=100000;app->poll();
     sign(status,false,sequence++);web.routes[status]();assert(web.status==200);
     if(web.response.find("AWAITING_EXPORT")!=std::string::npos){waiting=true;break;}
   }
   assert(waiting&&st.writes==1&&evidence->size()>0);
   // Without a durable-export receipt there must be no second target packet.
   for(unsigned n=0;n<3;++n){rocellConfiguredClock.tick+=100000;app->poll();}
   assert(st.writes==1);
   if(argc>2){
     auto request=[&](const char* path,bool post){
       sign(path,post,sequence);web.routes[path]();assert(web.status==200);
       std::cout<<sequence++<<" "<<web.status<<" "<<web.response<<" "
                <<web.out["X-Rocell-Signature"]<<std::endl;
     };
     const unsigned expected_legs=argc>1&&std::string(argv[1])=="local_interval_campaign"?11:12;
     for(unsigned leg=0;leg<expected_legs;++leg){
       if(leg){
         bool ready=false;
         for(unsigned n=0;n<40;++n){
           rocellConfiguredClock.tick+=100000;app->poll();web.body.clear();
           sign(status,false,sequence++);web.routes[status]();assert(web.status==200);
           if(web.response.find("AWAITING_EXPORT")!=std::string::npos){ready=true;break;}
         }
         assert(ready&&st.writes==leg+1);
       }
       web.body.clear();request("/rocell/characterization/record-info",false);
       const auto info=web.response;assert(info.size()==70);
       const unsigned size=std::stoul(info.substr(2,4),nullptr,16);
       for(unsigned offset=0;offset<size;){
         char position[5];snprintf(position,sizeof(position),"%04x",offset);
         web.body=info.substr(0,2)+position+info.substr(6);
         request("/rocell/characterization/record-chunk",true);
         assert(!web.response.empty());offset+=web.response.size()/2;
       }
       std::getline(std::cin,web.body);assert(!web.body.empty());
       if(web.body=="ABORT"){
         // Missing export receipt must time out, never dispatch the next leg.
         for(unsigned n=0;n<61;++n){rocellConfiguredClock.tick+=100000;app->poll();}
         web.body.clear();sign(status,false,sequence++);web.routes[status]();
         assert(web.response.find("FAULT")!=std::string::npos&&st.writes==leg+1);
         std::cout<<"STOPPED "<<st.writes<<std::endl;return 0;
       }
       request("/rocell/characterization/receipt",true);assert(web.response=="01");
     }
     app->poll();web.body.clear();sign(status,false,sequence++);web.routes[status]();
     assert(web.response.find("COMPLETE")!=std::string::npos&&st.writes==expected_legs);
     assert(evidence->size()==0);
     std::cout<<"COMPLETE "<<st.writes<<std::endl;
   }
 }
 std::cout<<"composition_bytes="<<sizeof(Composition)<<" evidence_bytes="<<sizeof(*evidence)<<"\n";
}
