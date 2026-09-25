#include <windows.h>
#include <bcrypt.h>
#include <fstream>
#include <vector>
#include <iterator>
#include <memory>
#include <cassert>
#include <iostream>
#include "characterization_admission.h"
#include "characterization_session.h"
#include "characterization_transport.h"
struct Crypto {
 bool hash(const uint8_t* key,const uint8_t* data,size_t size,uint8_t* out){
   BCRYPT_ALG_HANDLE a=nullptr;BCRYPT_HASH_HANDLE h=nullptr;
   if(BCryptOpenAlgorithmProvider(&a,BCRYPT_SHA256_ALGORITHM,nullptr,key?BCRYPT_ALG_HANDLE_HMAC_FLAG:0)<0)return false;
   auto r=BCryptCreateHash(a,&h,nullptr,0,const_cast<PUCHAR>(key),key?32:0,0);
   if(r>=0)r=BCryptHashData(h,const_cast<PUCHAR>(data),ULONG(size),0);
   if(r>=0)r=BCryptFinishHash(h,out,32,0);
   if(h)BCryptDestroyHash(h);BCryptCloseAlgorithmProvider(a,0);return r>=0;
 }
 bool hmac_sha256(const uint8_t (&key)[32],const uint8_t* p,size_t n,uint8_t (&out)[32]){return hash(key,p,n,out);}
 bool sha256(const uint8_t* p,size_t n,uint8_t (&out)[32]){return hash(nullptr,p,n,out);}
};
struct Clock {uint64_t tick=1001;uint64_t now_us(){return tick+=100;}};
struct Bus {
 int End=0,Error=0;unsigned writes=0,reads=0;
 int forward0=9,forward1=-7,reverse0=9,reverse1=-7;
 bool fail_reverse=false,fail_all=false;
 bool band_model=false,validation_model=false,bad_lower=false,ghost_small_model=false;
 bool ghost_delayed_reverse_model=false,ghost_pending=false;
 unsigned ghost_reverse_scans=0;
 int reverse_model=0;unsigned reverse_scans=0;
 uint16_t reverse_start[2]={};
 uint16_t p[7]={2047,2414,1702,2904,1591,2041,2047},g[7]={2047,2405,1709,2907,1589,2040,2047};
 int Read(uint8_t id,uint8_t address,uint8_t* out,uint8_t size){
   ++reads;memset(out,0,size);int i=id-11;
   if(ghost_pending&&id==11&&address==56){
     if(++ghost_reverse_scans>=8){p[1]=2388;p[2]=1727;ghost_pending=false;}
   }
   if(reverse_model&&writes==2&&id==11&&address==56){
     ++reverse_scans;
     if(reverse_model==1){ // Visible transient, then return near starting pose.
       p[1]=reverse_start[0]+(reverse_scans<=2?4:0);
       p[2]=reverse_start[1]-(reverse_scans<=2?4:2);
     }else if(reverse_scans>=8){p[1]=g[1]+forward0;p[2]=g[2]+forward1;fail_reverse=false;}
   }
   auto value=address==40?1:address==42?g[i]:address==56?p[i]:0;
   out[0]=value&255;if(size>1)out[1]=value>>8;return size;
 }
 void SyncWritePosEx(uint8_t*,uint8_t,int16_t* targets,uint16_t*,uint8_t*){
   const bool ghost_delayed_reverse=ghost_delayed_reverse_model&&g[1]==2388&&targets[0]==2386;
   const bool reverse=targets[0]>g[1];
   if(reverse){reverse_start[0]=p[1];reverse_start[1]=p[2];}
   ++writes;g[1]=targets[0];g[2]=targets[1];
   if(ghost_delayed_reverse){ghost_pending=true;ghost_reverse_scans=0;return;}
   if(fail_all||(reverse&&fail_reverse))return; // Test-only frozen actuator, goals still update.
   if(validation_model){
     if(g[1]==2389){p[1]=2391;p[2]=1724;}
     else if(g[1]==2377){p[1]=bad_lower?2383:2385;p[2]=bad_lower?1733:1731;}
     else if(g[1]==2378){p[1]=2387;p[2]=1730;}
     else if(g[1]==2379||g[1]==2381||g[1]==2383){p[1]=2387;p[2]=1730;}
     else if(g[1]==2385){p[1]=2387;p[2]=1728;}
     else if(g[1]==2386){p[1]=2388;p[2]=1727;}
     else if(g[1]==2387){p[1]=2389;p[2]=1726;}
     else if(g[1]==2388){p[1]=ghost_small_model?2389:2390;
                            p[2]=ghost_small_model?1726:1725;}
     return;
   }
   if(band_model){
     p[1]=p[1]<g[1]+2?g[1]+2:p[1]>g[1]+9?g[1]+9:p[1];
     p[2]=p[2]<g[2]-7?g[2]-7:p[2]>g[2]-1?g[2]-1:p[2];
     return;
   }
   p[1]=g[1]+(reverse?reverse0:forward0);
   p[2]=g[2]+(reverse?reverse1:forward1);
 }
};
int main(int argc,char** argv){
 std::cout<<"session_bytes="<<sizeof(rocell_diag::CharacterizationSession<Crypto>)<<"\n";
 assert(argc==4||argc==5||argc==6);std::ifstream file(argv[1],std::ios::binary);
 std::vector<uint8_t> token((std::istreambuf_iterator<char>(file)),{});
 uint8_t key[32],boot[16],nonce[32],campaign[32],reference[32];
 for(int i=0;i<32;++i){key[i]=i;nonce[i]=0x22;campaign[i]=0x33;reference[i]=0x44;}
 for(auto& b:boot)b=0x11;
 rocell_diag::CharacterizationManifest manifest;manifest.legs=2;
 manifest.goals[0][0]=2397;manifest.goals[0][1]=1717;
 manifest.goals[1][0]=2405;manifest.goals[1][1]=1709;
 for(auto& bound:manifest.bounds){bound[0]=0;bound[1]=4095;}
 rocell_diag::CharacterizationAdmission admission(key,boot,nonce,1000,11000,campaign,reference,manifest);
 auto owner=std::make_unique<rocell_diag::ShoulderCharacterizationOwner>();Crypto crypto;
 bool accepted=admission.start(token.data(),token.size(),strtoull(argv[2],nullptr,10),crypto,*owner);
 assert(accepted==(strcmp(argv[3],"yes")==0));
 assert(owner->writes()==0);
 assert(!admission.start(token.data(),token.size(),1001,crypto,*owner));
 assert(owner->phase()==(accepted?rocell_diag::CharacterizationPhase::Baseline:rocell_diag::CharacterizationPhase::New));
 if(argc>=5){
   auto session=std::make_unique<rocell_diag::CharacterizationSession<Crypto>>(crypto,key,boot,nonce,1000,11000,campaign,reference,manifest);
   Bus bus;Clock clock;auto evidence=[](auto...){return true;};auto allowed=[](){return true;};
   bool authenticated=false;
   auto access=[&](){return authenticated?session.get():nullptr;};
   rocell_diag::CharacterizationTransport<decltype(access),Clock> transport(access,clock);
   uint8_t response[1024];size_t response_size;
   using Request=rocell_diag::CampaignRequest;
   assert(transport.dispatch(Request::Start,token.data(),token.size(),response,sizeof(response),response_size)==403);
   assert(!bus.reads&&!bus.writes);authenticated=true;
   unsigned record_leg;size_t record_size;uint8_t record_digest[32];
   assert(!session->record_info(record_leg,record_size,record_digest));
   session->advance(bus,clock,evidence,allowed);assert(!bus.reads&&!bus.writes);
   assert(transport.dispatch(Request::Start,token.data(),token.size(),response,sizeof(response),response_size)==200);
   assert(!session->start(token.data(),token.size(),1002));
   uint8_t prior[124]={};bool wrong=strcmp(argv[4],"wrong-campaign")==0;
   bool replay=strcmp(argv[4],"replay")==0,missing=strcmp(argv[4],"missing")==0;
   for(int i=0;i<100;++i){
     clock.tick+=200000;session->advance(bus,clock,evidence,allowed);
     if(session->phase()==rocell_diag::CharacterizationPhase::AwaitExport){
       auto reads_before=bus.reads,writes_before=bus.writes;
       assert(session->record_info(record_leg,record_size,record_digest));
       assert(transport.dispatch(Request::RecordInfo,nullptr,0,response,sizeof(response),response_size)==200&&response_size==35);
       uint8_t request[35];memcpy(request,response,35);request[1]=request[2]=0;
       assert(transport.dispatch(Request::RecordChunk,request,35,response,sizeof(response),response_size)==200);
       assert(response_size>0&&!memcmp(response,session->result_bytes(),response_size));
       assert(transport.dispatch(Request::RecordChunk,request,34,response,sizeof(response),response_size)==400);
       std::vector<uint8_t> assembled;uint8_t chunk[1024];size_t copied=99;
       assert(!session->record_chunk(record_leg+1,record_digest,0,chunk,1024,copied)&&copied==0);
       record_digest[0]^=1;assert(!session->record_chunk(record_leg,record_digest,0,chunk,1024,copied));record_digest[0]^=1;
       assert(!session->record_chunk(record_leg,record_digest,record_size,chunk,1024,copied));
       assert(!session->record_chunk(record_leg,record_digest,0,chunk,1025,copied));
       for(size_t offset=0;offset<record_size;offset+=copied){
         assert(session->record_chunk(record_leg,record_digest,offset,chunk,1024,copied));
         assembled.insert(assembled.end(),chunk,chunk+copied);
       }
       assert(assembled.size()==session->result_size());
       assert(!memcmp(assembled.data(),session->result_bytes(),assembled.size()));
       assert(bus.reads==reads_before&&bus.writes==writes_before);
       if(argc==6&&record_leg==0){std::ofstream output(argv[5],std::ios::binary);
         output.write(reinterpret_cast<const char*>(assembled.data()),assembled.size());assert(output.good());}
       if(missing){clock.tick+=5000001;session->advance(bus,clock,evidence,allowed);break;}
       uint8_t receipt[124]={},digest[32],signature[32];memcpy(receipt,"RCSHEX01",8);memcpy(receipt+8,boot,16);
       const char* name=wrong?"other-campaign":session->campaign_id();
       assert(crypto.sha256(reinterpret_cast<const uint8_t*>(name),strlen(name),digest));memcpy(receipt+24,digest,32);
       receipt[56]=session->completed();
       assert(crypto.sha256(session->result_bytes(),session->result_size(),digest));memcpy(receipt+60,digest,32);
       assert(crypto.hmac_sha256(key,receipt,92,signature));memcpy(receipt+92,signature,32);
       if(replay&&session->completed()==1)memcpy(receipt,prior,124);
       transport.dispatch(Request::Receipt,receipt,124,response,sizeof(response),response_size);memcpy(prior,receipt,124);
     }
     if(session->phase()==rocell_diag::CharacterizationPhase::Fault||session->phase()==rocell_diag::CharacterizationPhase::Complete)break;
   }
   const bool success=!wrong&&!replay&&!missing;
   assert((session->phase()==rocell_diag::CharacterizationPhase::Complete)==success);
   assert(bus.writes==(wrong||missing?1:2));
   auto reads=bus.reads;session->advance(bus,clock,evidence,allowed);assert(reads==bus.reads);
   // Faults retain their last staged record for post-stop diagnostics. A
   // completed session must not expose an old record as a fresh result.
   assert(session->record_info(record_leg,record_size,record_digest)==!success);
   if(!success)assert(transport.dispatch(Request::Fault,nullptr,0,response,sizeof(response),response_size)==200);
 }
}
