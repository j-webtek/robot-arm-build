// Strict, one-use receipt for initial elbow T101 diagnostics. Does not authorize
// movement, convert targets, or touch the bus. Exact accepted payload is retained.
#pragma once
#include <ArduinoJson.h>
#include <math.h>
#include "servo_evidence_json.h"
namespace rocell_diag {
class DiagnosticReceipt {
 public:
  DiagnosticReceipt():used_(false),accepted_(false),rad_(0),speed_(0),acc_(0),
      received_us_(0),boot_{},command_{},payload_{} {}
  bool accept(const char* boot,const char* command,const char* payload,size_t length,uint64_t when) {
    if(used_)return false;
    used_=true;
    if(!valid_identity(boot)||!valid_identity(command)||!payload||!length||length>256||when>INT64_MAX)
      return false;
    // ArduinoJson accepts duplicate keys/trailing input. Restrict this protocol
    // to one flat object with exactly five members BEFORE parsing. Nested values
    // are not legal T101 numeric fields; quoted colons do not count as members.
    bool quoted=false,escaped=false,opened=false,closed=false;unsigned colons=0,strings=0;
    for(size_t i=0;i<length;++i){
      const char c=payload[i];if(!c)return false;
      if(quoted){if(escaped)escaped=false;else if(c=='\\')escaped=true;else if(c=='"')quoted=false;continue;}
      if(c==' '||c=='\n'||c=='\r'||c=='\t')continue;
      if(closed)return false;
      if(!opened){if(c!='{')return false;opened=true;continue;}
      if(c=='"'){quoted=true;++strings;}
      else if(c=='{'||c=='['||c==']')return false;
      else if(c=='}')closed=true;
      else if(c==':')++colons;
    }
    if(!closed||quoted||colons!=5||strings!=5)return false;
    memcpy(payload_,payload,length);payload_[length]=0;
    JsonDocument doc;
    if(deserializeJson(doc,static_cast<const char*>(payload_),length) || !doc.is<JsonObject>() || doc.size()!=5)
      return false;
    if(!doc["T"].is<int>()||doc["T"].as<int>()!=101 ||
       !doc["joint"].is<int>()||doc["joint"].as<int>()!=3 ||
       !doc["rad"].is<double>()||!isfinite(doc["rad"].as<double>()) ||
       !doc["spd"].is<uint16_t>()||doc["spd"].as<uint16_t>()==0 ||
       !doc["acc"].is<uint8_t>()||doc["acc"].as<uint8_t>()==0)return false;
    memcpy(boot_,boot,strlen(boot)+1);memcpy(command_,command,strlen(command)+1);
    rad_=doc["rad"].as<double>();speed_=doc["spd"].as<uint16_t>();acc_=doc["acc"].as<uint8_t>();
    received_us_=when;accepted_=true;return true;
  }
  bool encode(char* output,size_t capacity) const {
    if(!output||!capacity)return false;output[0]=0;if(!accepted_)return false;
    JsonDocument doc;
    doc["schema"]="rocell.controller_receipt.v1";
    doc["boot_id"]=boot_;doc["command_id"]=command_;doc["received_us"]=received_us_;
    doc["payload_utf8"]=payload_;doc["joint"]=3;doc["received_rad"]=rad_;
    char parsed_rad[32];snprintf(parsed_rad,sizeof(parsed_rad),"%.17g",rad_);
    doc["received_rad_text"]=parsed_rad; // Round-trip value independent of JSON float formatting.
    doc["speed"]=speed_;doc["acceleration"]=acc_;
    if(doc.overflowed()||measureJson(doc)>=capacity)return false;
    return serializeJson(doc,output,capacity)>0;
  }
  double received_radians() const {return rad_;}
  const char* boot_id() const {return boot_;}
  const char* command_id() const {return command_;}
  uint16_t speed() const {return speed_;}
  uint8_t acceleration() const {return acc_;}
 private:
  bool used_,accepted_;double rad_;uint16_t speed_;uint8_t acc_;
  uint64_t received_us_;char boot_[129],command_[129],payload_[257];
};
}
