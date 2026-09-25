#include "shoulder_characterization_owner.h"
#include "characterization_fault_record.h"
#include <cassert>
#include <iostream>
#include <memory>
#include <string>
#include <fstream>
#include <windows.h>
#include <bcrypt.h>
struct Crypto {
 bool hash(const uint8_t* key,const uint8_t* data,size_t size,uint8_t* out){
   BCRYPT_ALG_HANDLE a=nullptr;BCRYPT_HASH_HANDLE h=nullptr;
   if(BCryptOpenAlgorithmProvider(&a,BCRYPT_SHA256_ALGORITHM,nullptr,key?BCRYPT_ALG_HANDLE_HMAC_FLAG:0)<0)return false;
   auto r=BCryptCreateHash(a,&h,nullptr,0,const_cast<PUCHAR>(key),key?32:0,0);
   if(r>=0)r=BCryptHashData(h,const_cast<PUCHAR>(data),ULONG(size),0);
   if(r>=0)r=BCryptFinishHash(h,out,32,0);
   if(h)BCryptDestroyHash(h);BCryptCloseAlgorithmProvider(a,0);return r>=0;
 }
 bool sha256(const uint8_t* p,size_t n,uint8_t (&out)[32]){return hash(nullptr,p,n,out);}
 bool hmac_sha256(const uint8_t (&key)[32],const uint8_t* p,size_t n,uint8_t (&out)[32]){return hash(key,p,n,out);}
};
struct Clock{uint64_t tick=1;uint64_t now_us(){return tick+=100;}};
struct Bus{
  int End=0,Error=0;unsigned writes=0,reads=0;std::string mode;
  uint16_t p[7]={2047,2414,1702,2904,1591,2041,2047},g[7]={2047,2405,1709,2907,1589,2040,2047};
  int Read(uint8_t sid,uint8_t address,uint8_t* out,uint8_t width){
    ++reads;memset(out,0,width);int i=sid-11;
    if(mode=="read_failure"&&writes==4)return 0;
    int value=address==40?1:address==42?g[i]:address==56?p[i]:0;
    if(mode=="torque"&&writes==4&&sid==12&&address==40)value=0;
    out[0]=value&255;if(width>1)out[1]=value>>8;
    if(mode=="unsettled"&&writes==4&&sid==12&&address==56)out[2]=1;
    return width;
  }
  void SyncWritePosEx(uint8_t* ids,uint8_t n,int16_t* targets,uint16_t* speed,uint8_t* acc){
    assert(n==2&&ids[0]==12&&ids[1]==13&&speed[0]==20&&speed[1]==20&&acc[0]==1&&acc[1]==1);
    int old=p[1],direction=targets[0]>g[1]?1:-1;++writes;
    g[1]=targets[0];g[2]=targets[1];
    if(mode=="no_response"&&writes==4)return;
    p[1]=g[1]+(mode=="accurate"?0:9);p[2]=g[2]-(mode=="accurate"?0:7);
    if(writes==4){
      if(mode=="neighbor")p[4]+=3;
      if(mode=="reverse")p[1]=old-direction*3;
      if(mode=="wrong_goal")g[1]++;
    }
  }
};
int main(int argc,char** argv){
  assert(argc==2||argc==3);Bus bus;bus.mode=argv[1];Clock clock;
  if(bus.mode=="accurate"){bus.p[1]=bus.g[1];bus.p[2]=bus.g[2];}
  rocell_diag::CharacterizationManifest manifest;manifest.legs=12;
  int offsets[4]={-8,0,-16,0};
  for(int n=0;n<12;++n){manifest.goals[n][0]=2405+offsets[n%4];manifest.goals[n][1]=1709-offsets[n%4];}
  for(int i=0;i<7;++i){manifest.bounds[i][0]=bus.p[i]-32;manifest.bounds[i][1]=bus.p[i]+32;}
  if(bus.mode=="manifest")manifest.goals[4][0]++;
  auto owner=std::make_unique<rocell_diag::ShoulderCharacterizationOwner>();
  Crypto crypto;uint8_t key[32]={1},boot[16]={2},prior_receipt[124]={};
  rocell_diag::CharacterizationExportBarrier<Crypto> barrier(crypto,key,boot,"campaign-test");
  bool ok=owner->begin(manifest,clock.now_us());
  assert(!owner->begin(manifest,clock.now_us())); // No restart/reuse.
  unsigned results=0;bool delay=false;
  auto evidence=[&](const char* event,unsigned leg,const rocell_diag::ShoulderPreloadPose&,const rocell_diag::CharacterizationResult* r){
    if(bus.mode=="export"&&leg==3&&strcmp(event,"RESULT")==0)return false;
    if(bus.mode=="intent_export"&&leg==3&&strcmp(event,"INTENT")==0)return false;
    if(bus.mode=="prewrite_delay"&&leg==3&&strcmp(event,"PREWRITE")==0)clock.tick+=200000;
    if(strcmp(event,"RESULT")==0){assert(r);++results;}
    return true;
  };
  auto admission=[&](){return !(bus.mode=="cancel"&&owner->completed()==3);};
  for(unsigned n=0;n<1000&&ok;++n){
    clock.tick+=200000;
    if(bus.mode=="deadline"&&owner->completed()==3&&!delay){clock.tick+=60000000;delay=true;}
    owner->advance(bus,clock,evidence,admission);
    if(owner->phase()==rocell_diag::CharacterizationPhase::AwaitExport){
      const auto reads=bus.reads,writes=bus.writes;
      owner->advance(bus,clock,evidence,admission);
      assert(bus.reads==reads&&bus.writes==writes); // Waiting cannot touch bus.
      assert(owner->stage_export(barrier,clock.now_us()));
      if(argc==3&&owner->completed()==0){
        std::ofstream artifact(argv[2],std::ios::binary);
        artifact.write(reinterpret_cast<const char*>(owner->result_bytes()),owner->result_size());
        assert(artifact.good());
      }
      if(bus.mode=="delayed_receipt")clock.tick+=1200000;
      uint8_t token[124]={},digest[32],signature[32];
      memcpy(token,"RCSHEX01",8);memcpy(token+8,boot,16);
      assert(crypto.sha256(reinterpret_cast<const uint8_t*>("campaign-test"),13,digest));
      memcpy(token+24,digest,32);token[56]=owner->completed();
      assert(crypto.sha256(owner->result_bytes(),owner->result_size(),digest));
      memcpy(token+60,digest,32);
      assert(crypto.hmac_sha256(key,token,92,signature));memcpy(token+92,signature,32);
      if(owner->completed()==3){
        if(bus.mode=="receipt_replay")memcpy(token,prior_receipt,124);
        if(bus.mode=="receipt_tamper")token[60]^=1;
        if(bus.mode=="receipt_expired")clock.tick+=5000001;
        if(bus.mode=="export_interrupted"){
          clock.tick+=5000001;owner->advance(bus,clock,evidence,admission);break;
        }
        if(bus.mode=="post_export_drift")bus.p[1]+=3;
      }
      owner->accept_export(barrier,{token,124},clock.now_us());
      memcpy(prior_receipt,token,124);
    }
    if(owner->phase()==rocell_diag::CharacterizationPhase::Complete||owner->phase()==rocell_diag::CharacterizationPhase::Fault)break;
  }
  const bool success=bus.mode=="miss"||bus.mode=="accurate"||bus.mode=="delayed_receipt";
  assert((owner->phase()==rocell_diag::CharacterizationPhase::Complete)==success);
  unsigned expected=success?12:bus.mode=="manifest"?0:
    (bus.mode=="cancel"||bus.mode=="deadline"||bus.mode=="intent_export"||bus.mode=="prewrite_delay")?3:4;
  assert(bus.writes==expected&&owner->writes()==expected);
  if(success){assert(results==12&&owner->completed()==12);assert(owner->misses()==(bus.mode=="accurate"?0:12));}
  else assert(owner->completed()==(bus.mode=="manifest"?0:bus.mode=="post_export_drift"?4:3));
  auto reads=bus.reads;for(int i=0;i<10;++i)owner->advance(bus,clock,evidence,admission);
  assert(bus.writes==expected&&bus.reads==reads);
  if(!success&&bus.mode!="manifest"){
    assert(owner->fault().present&&owner->fault().writes==expected);
    auto reason=owner->fault().reason;
    owner->accept_export(barrier,{nullptr,0},clock.now_us());
    assert(owner->fault().reason==reason); // First failure survives later requests.
    uint8_t record[256]={};
    assert(!rocell_diag::encode_characterization_fault(owner->fault(),record,1));
    auto size=rocell_diag::encode_characterization_fault(owner->fault(),record,sizeof(record));
    assert(size>0);
    if(argc==3){std::ofstream file(std::string(argv[2])+".fault",std::ios::binary);
      file.write(reinterpret_cast<const char*>(record),size);assert(file.good());}
  }
  std::cout<<"OWNER_PASSED "<<bus.writes<<" "<<owner->reason()<<"\n";
}
