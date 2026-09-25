// Offline candidate. No bus, write, reset or torque API. The future owning
// controller must supply its own three exported records, never request-body
// replacements. Allocate this object off the control-task stack.
#pragma once
#include "compensated_shoulder_contract.h"
#include "start_envelope.h"
#include "hold_evidence_json.h"
namespace rocell_diag {
class CompensatedShoulderAuthorization {
 public:
  CompensatedShoulderAuthorization(const uint8_t (&key)[32],const uint8_t (&boot)[16],
      const uint8_t (&nonce)[32],uint64_t issued,uint64_t expires,const char* command)
      :gate_(key,boot,nonce,issued,expires){
    const char* hex="0123456789abcdef";
    for(unsigned i=0;i<16;++i){boot_[2*i]=hex[boot[i]>>4];boot_[2*i+1]=hex[boot[i]&15];}
    if(valid_identity(command)&&strlen(command)<=100)strcpy(command_,command);
  }
  template<class Crypto>
  bool verify(const uint8_t* token,size_t length,uint64_t now,Crypto& crypto,
      const char* const (&records)[3],const size_t (&sizes)[3]){
    if(attempted_)return false;attempted_=true;
    AuthenticatedPlanView plan;
    if(!command_[0]||!gate_.consume(token,length,now,crypto,plan)||plan.length>2048)return false;
    size_t offset=0;uint64_t last=0;char capture[129]={};
    ShoulderPreloadPose first,current;
    for(unsigned n=0;n<3;++n){
      if(!records[n]||!sizes[n]||sizes[n]>4095)return false;
      JsonDocument doc;if(deserializeJson(doc,records[n],sizes[n]))return false;
      const char* source=doc["command_id"]|"";
      if(!valid_identity(source)||doc["schema"]!="rocell.shoulder_hold_event.v1"||
          doc["boot_id"]!=boot_||doc["snapshot_role"]!="OBSERVATION"||
          !doc["physical_accuracy_verified"].is<bool>()||doc["physical_accuracy_verified"].as<bool>()||
          !doc["scan_started_us"].is<uint64_t>()||!doc["scan_finished_us"].is<uint64_t>())return false;
      if(!n)strcpy(capture,source);else if(strcmp(capture,source))return false;
      current={};current.started_us=doc["scan_started_us"].as<uint64_t>();
      current.finished_us=doc["scan_finished_us"].as<uint64_t>();
      if(current.started_us<=last||current.finished_us<current.started_us||
          current.finished_us-current.started_us>300000||
          (n&&current.started_us-last<100000))return false;
      JsonArrayConst rows=doc["joints"].as<JsonArrayConst>();if(rows.size()!=7)return false;
      for(unsigned i=0;i<7;++i){
        auto row=rows[i].as<JsonArrayConst>();
        if(row.size()!=5||!row[0].is<unsigned>()||row[0].as<unsigned>()!=i+11||
            !row[1].is<uint16_t>()||!row[2].is<uint16_t>()||!row[3].is<unsigned>()||row[3].as<unsigned>()!=1)return false;
        current.position[i]=row[1].as<uint16_t>();current.goal[i]=row[2].as<uint16_t>();current.torque[i]=1;
        const char* raw=row[4]|"";if(strlen(raw)!=30)return false;
        for(unsigned j=0;j<30;++j){
          char c=raw[j];int digit=c>='0'&&c<='9'?c-'0':c>='a'&&c<='f'?c-'a'+10:-1;
          if(digit<0)return false;
          if(j%2==0)current.feedback[i][j/2]=digit<<4;else current.feedback[i][j/2]|=digit;
        }
        if((current.feedback[i][0]|(uint16_t(current.feedback[i][1])<<8))!=current.position[i])return false;
        if(n&&(current.goal[i]!=first.goal[i]||std::abs(int(current.position[i])-int(first.position[i]))>1))return false;
      }
      if(!LocalShoulderStepContract::stationary(current))return false;
      if(!n)first=current;last=current.finished_us;
      for(int shift=24;shift>=0;shift-=8)reference_bytes_[offset++]=uint8_t(sizes[n]>>shift);
      memcpy(reference_bytes_+offset,records[n],sizes[n]);offset+=sizes[n];
    }
    if(!contract_.prepare(current,now))return false;
    uint8_t digest[32];if(!crypto.sha256(reference_bytes_,offset,digest))return false;
    char hash[65]={};const char* hex="0123456789abcdef";
    for(unsigned i=0;i<32;++i){hash[2*i]=hex[digest[i]>>4];hash[2*i+1]=hex[digest[i]&15];}
    // Rebuild every allowed field. Exact byte equality rejects extra/duplicate
    // fields, altered parameters, wrong identities and noncanonical JSON.
    JsonDocument expected;
    expected["schema"]="rocell.compensated_shoulder_step.v1";expected["boot_id"]=boot_;
    expected["command_id"]=command_;expected["reference_sha256"]=hash;
    expected["reference_finished_us"]=current.finished_us;
    auto positions=expected["positions"].to<JsonArray>();auto goals=expected["goals"].to<JsonArray>();
    for(unsigned i=0;i<7;++i){positions.add(current.position[i]);goals.add(current.goal[i]);}
    expected["model_id"]="r29-frozen-offset-v1";
    auto offsets=expected["offsets"].to<JsonArray>();offsets.add(10);offsets.add(-7);
    auto desired=expected["desired_positions"].to<JsonArray>();
    auto commands=expected["command_goals"].to<JsonArray>();
    auto predicted=expected["predicted_positions"].to<JsonArray>();
    for(int i=0;i<2;++i){desired.add(contract_.desired[i]);commands.add(contract_.command_goals[i]);predicted.add(contract_.predicted[i]);}
    expected["goal_sum"]=4114;
    expected["speed"]=20;expected["acceleration"]=1;expected["maximum_target_packets"]=1;expected["arrival_tolerance_counts"]=2;
    if(!hold_json_finish(expected,canonical_,sizeof(canonical_))||
       strlen(canonical_)!=plan.length||memcmp(canonical_,plan.bytes,plan.length))return false;
    verified_=true;return true;
  }
  const CompensatedShoulderContract* contract()const{return verified_?&contract_:nullptr;}
 private:
  StartEnvelopeGate gate_;CompensatedShoulderContract contract_;
  bool attempted_=false,verified_=false;
  char boot_[33]={},command_[101]={},canonical_[2049]={};
  uint8_t reference_bytes_[3*(4095+4)]={};
};
}
